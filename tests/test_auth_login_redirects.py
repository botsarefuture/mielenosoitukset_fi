from urllib.parse import unquote, urlsplit

import pytest


def test_login_does_not_redirect_back_to_notifications_api(client, seeded_data):
    response = client.post(
        "/users/auth/login?next=/api/notifications/",
        data={
            "username": seeded_data["user_username"],
            "password": "UserPass1!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert "/api/notifications/" not in response.headers["Location"]


@pytest.mark.parametrize('target', ['/users/profile/', '/users/profile/?tab=security#settings', '/city/Helsinki?source=login'])
def test_login_keeps_normal_internal_page_redirect(client, seeded_data, target):
    response = client.post(
        "/users/auth/login", query_string={'next': target},
        data={
            "username": seeded_data["user_username"],
            "password": "UserPass1!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == target
    with client.session_transaction() as session:
        assert session['_user_id'] == str(seeded_data['user_id'])


@pytest.mark.parametrize('target', [
    'https://outside.example/path', '//outside.example/path', '///outside.example/path',
    '/\\outside.example/path', '\\\\outside.example/path',
    'javascript:alert(1)', '../relative', ' /users/profile/',
    '/\t/outside.example/path', '/users/profile/\r\nLocation: https://outside.example',
    '/users/auth/login?next=/users/profile/', '/users/auth/login/#again',
    '/api/notifications/?page=1', '/users/auth/api/v2/step-up/status',
    '/users/auth/./login', '/ignored/../users/auth/login?popup=1',
    '/users/auth/%2e/login', '/ignored/../api/notifications/', '/api%2fnotifications/',
])
@pytest.mark.parametrize('popup', [False, True])
def test_login_rejects_unsafe_or_non_page_return_targets(client, seeded_data, target, popup):
    response = client.post('/users/auth/login', query_string={'next': target, 'popup': '1' if popup else '0'}, data={
        'username': seeded_data['user_username'], 'password': 'UserPass1!',
    })
    if popup:
        assert response.status_code == 200
        assert 'window.location = "/";' in response.get_data(as_text=True)
    else:
        assert response.status_code == 302
        assert response.headers['Location'] == '/'
    with client.session_transaction() as session:
        assert session['_user_id'] == str(seeded_data['user_id'])


@pytest.mark.e2e
@pytest.mark.parametrize('target', [
    '/";console.log("LOGIN_REDIRECT_INJECTED");//',
    '/</script><script>console.log("LOGIN_REDIRECT_INJECTED")</script>',
])
def test_popup_login_return_target_is_data_not_executable_script(client, seeded_data, browser_page, target):
    response = client.post('/users/auth/login', query_string={'next': target, 'popup': '1'}, data={
        'username': seeded_data['user_username'], 'password': 'UserPass1!',
    })
    assert response.status_code == 200
    document = response.get_data(as_text=True)
    messages, errors, navigations = [], [], []
    browser_page.on('console', lambda message: messages.append(message.text))
    browser_page.on('pageerror', lambda error: errors.append(str(error)))

    def serve(route):
        if urlsplit(route.request.url).path == '/popup-test':
            route.fulfill(content_type='text/html', body=document)
        else:
            navigations.append(route.request.url)
            route.fulfill(content_type='text/html', body='<p id="arrived">Internal destination</p>')

    # Every browser request is fulfilled locally, including any attempted escape.
    browser_page.route('**/*', serve)
    browser_page.goto('http://127.0.0.1/popup-test', wait_until='commit')
    browser_page.wait_for_function("document.readyState === 'complete'")
    assert not any('LOGIN_REDIRECT_INJECTED' in message for message in messages)
    assert not errors
    browser_page.locator('#arrived').wait_for()
    assert len(navigations) == 1
    destination = urlsplit(navigations[0])
    assert destination.netloc == '127.0.0.1'
    assert unquote(destination.path) == target
    assert not any('LOGIN_REDIRECT_INJECTED' in message for message in messages)
    assert not errors


@pytest.mark.e2e
def test_popup_login_still_reloads_opener_and_closes(client, seeded_data, browser_page):
    response = client.post('/users/auth/login', query_string={'next': '/users/profile/', 'popup': '1'}, data={
        'username': seeded_data['user_username'], 'password': 'UserPass1!',
    })
    assert response.status_code == 200
    reloads = []
    context = browser_page.context

    def serve(route):
        path = urlsplit(route.request.url).path
        if path == '/opener-test':
            reloads.append(path)
            route.fulfill(content_type='text/html', body='''<button id="open-login" type="button"
              onclick="window.open('/popup-test', 'login')">Sign in</button>''')
        elif path == '/popup-test':
            route.fulfill(content_type='text/html', body=response.get_data(as_text=True))
        else:
            route.fulfill(status=404, body='Unexpected destination')

    context.route('**/*', serve)
    browser_page.goto('http://127.0.0.1/opener-test')
    with browser_page.expect_popup() as opened:
        browser_page.locator('#open-login').click()
    popup = opened.value
    browser_page.wait_for_function("performance.getEntriesByType('navigation')[0].type === 'reload'")
    if not popup.is_closed():
        popup.wait_for_event('close')
    assert len(reloads) == 2
