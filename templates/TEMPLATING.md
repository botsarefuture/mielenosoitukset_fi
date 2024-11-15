# Templating Guide

This document provides an overview of the blocks defined in `base.html` and `admin_base.html` templates. These blocks can be overridden in child templates to customize the content and structure.

## Blocks in `base.html`

### `meta`
This block is used to insert additional meta tags in the head section of the HTML document.

```html
{% block meta %}
<!-- Additional meta tags go here -->
{% endblock %}
```

### `title`
This block is used to set the title of the HTML document.

```html
{% block title %}Mielenosoitukset.fi{% endblock %}
```

### `styles`
This block is used to insert additional stylesheets in the head section of the HTML document.

```html
{% block styles %}
<!-- Additional stylesheets go here -->
{% endblock %}
```

### `content`
This block is used to insert the main content of the HTML document.

```html
{% block content %}
<!-- Main content goes here -->
{% endblock %}
```

### `scripts`
This block is used to insert additional scripts before the closing body tag of the HTML document.

```html
{% block scripts %}
<!-- Additional scripts go here -->
{% endblock %}
```

## Blocks in `admin_base.html`

### `content`
This block is used to insert the main content of the admin dashboard.

```html
{% block content %}
<!-- Admin dashboard content goes here -->
{% endblock %}
```

### `main_content`
This block is used to insert the main content within the admin dashboard's content block.

```html
{% block main_content %}
<!-- Main content for admin dashboard goes here -->
{% endblock %}
```

By overriding these blocks in your child templates, you can customize the content and structure of your web pages.
## Roadmap for Blocks

To effectively use and override the blocks defined in `base.html` and `admin_base.html`, follow this roadmap:

1. **Identify the Block to Override**:
    - Review the blocks available in the parent templates (`base.html` and `admin_base.html`).
    - Determine which block you need to override to achieve your desired customization.

2. **Create a Child Template**:
    - Create a new HTML file that will serve as your child template.
    - Extend the parent template using the `{% extends %}` tag.

3. **Override the Block**:
    - Use the `{% block %}` tag to override the desired block in your child template.
    - Insert your custom content within the block.

4. **Test Your Changes**:
    - Render the child template in your web application.
    - Verify that the custom content appears as expected.

5. **Iterate as Needed**:
    - Make additional changes to the blocks as necessary.
    - Repeat the testing process to ensure everything works correctly.

### Example

Here's an example of how to override the `title` and `content` blocks in a child template:

```html
{% extends "base.html" %}

{% block title %}Custom Page Title{% endblock %}

{% block content %}
<p>This is the custom content for the page.</p>
{% endblock %}
```

By following this roadmap, you can effectively customize the content and structure of your web pages using the templating system.