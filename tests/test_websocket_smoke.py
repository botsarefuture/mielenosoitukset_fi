import pytest


@pytest.mark.integration
@pytest.mark.ws
def test_chat_socketio_events_cover_friend_listing_history_send_and_read(
    chat_app,
    chat_seeded_data,
):
    user_client = chat_app.test_client()
    friend_client = chat_app.test_client()

    with user_client.session_transaction() as session:
        session["_user_id"] = str(chat_seeded_data["user_id"])
        session["_fresh"] = True

    with friend_client.session_transaction() as session:
        session["_user_id"] = str(chat_seeded_data["friend_id"])
        session["_fresh"] = True

    socketio = chat_app.extensions["socketio"]
    user_socket = socketio.test_client(chat_app, flask_test_client=user_client)
    friend_socket = socketio.test_client(chat_app, flask_test_client=friend_client)

    assert user_socket.is_connected()
    assert friend_socket.is_connected()

    user_socket.get_received()
    friend_socket.get_received()

    user_socket.emit("get_friends")
    user_events = user_socket.get_received()
    friends_event = next(event for event in user_events if event["name"] == "friends_list")
    assert friends_event["args"][0]["friends"][0]["username"] == chat_seeded_data["friend_username"]

    user_socket.emit("load_messages", {"friend_username": chat_seeded_data["friend_username"]})
    user_events = user_socket.get_received()
    history_event = next(event for event in user_events if event["name"] == "chat_history")
    initial_messages = history_event["args"][0]["messages"]
    assert len(initial_messages) >= 1

    unread_message = initial_messages[0]
    user_socket.emit(
        "send_message",
        {
            "recipient": chat_seeded_data["friend_username"],
            "content": "Hello from websocket smoke",
            "type": "chat",
        },
    )
    friend_events = friend_socket.get_received()
    new_message_event = next(event for event in friend_events if event["name"] == "new_message")
    assert new_message_event["args"][0]["message"]["content"] == "Hello from websocket smoke"

    user_socket.emit("mark_read", {"message_id": unread_message["_id"]})
    friend_events = friend_socket.get_received()
    read_event = next(event for event in friend_events if event["name"] == "message_read")
    assert read_event["args"][0]["message_id"] == unread_message["_id"]

    user_socket.disconnect()
    friend_socket.disconnect()
