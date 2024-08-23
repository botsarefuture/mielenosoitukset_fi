# Container CSS Guide

## Overview

The `container.css` file provides styles for various container layouts used throughout the site. This guide explains the purpose and usage of each class within the stylesheet.

## General Container Styles

### `.container`
- **Description**: The default styling for the main container.
- **Styles**:
  - `max-width: 1200px;`: Limits the container's width to ensure readability.
  - `margin: 0 auto;`: Centers the container horizontally.
  - `padding: 20px;`: Adds padding inside the container.
  - `box-sizing: border-box;`: Ensures padding is included in the container's width.
  - `background-color: #E0E0E0;`: Sets the default background color for main content areas.

## Background Color Utility Classes

### `.bg-main-content`
- **Description**: Applies the default background color for main content areas.
- **Background Color**: `#E0E0E0`

### `.bg-highlight`
- **Description**: Highlights important areas such as call-to-action or announcement sections.
- **Background Color**: `#E8F5E9` (Light green)

### `.bg-warning`
- **Description**: Used for warning or call-to-action areas to draw attention.
- **Background Color**: `#FFF3E0` (Light orange)

### `.bg-header-footer`
- **Description**: Styles for headers and footers.
- **Background Color**: `#0033A0` (Dark blue)
- **Text Color**: `#FFFFFF` (White)

## Special Layout Containers

### `.container-fluid`
- **Description**: A container that spans the full width of the viewport.
- **Styles**:
  - `max-width: 100%;`: Allows the container to take the full width.
  - `padding: 20px;`: Adds padding inside the container.
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-centered`
- **Description**: Centers content both horizontally and vertically.
- **Styles**:
  - `display: flex;`
  - `flex-direction: column;`
  - `align-items: center;`: Centers items horizontally.
  - `justify-content: center;`: Centers items vertically.
  - `text-align: center;`: Centers text.
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-sidebar`
- **Description**: A layout with a fixed sidebar and main content area.
- **Styles**:
  - `display: flex;`
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-columns`
- **Description**: A flexible multi-column layout that wraps on smaller screens.
- **Styles**:
  - `display: flex;`
  - `flex-wrap: wrap;`
  - `gap: 20px;`: Space between columns.
  - `padding: 20px;`
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-form`
- **Description**: A container specifically for forms with vertical layout and spacing.
- **Styles**:
  - `display: flex;`
  - `flex-direction: column;`
  - `gap: 15px;`: Space between form elements.
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-grid`
- **Description**: A responsive grid layout.
- **Styles**:
  - `display: grid;`
  - `grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));`: Creates a responsive grid.
  - `gap: 20px;`: Space between grid items.
  - `padding: 20px;`
  - `background-color: #E0E0E0;`: Applies the default background color.

### `.container-align-items`
- **Description**: Aligns items centrally with space distributed between them.
- **Styles**:
  - `display: flex;`
  - `align-items: center;`: Centers items vertically.
  - `justify-content: space-between;`: Distributes space between items.
  - `background-color: #E0E0E0;`: Applies the default background color.

## Responsive Containers

### Media Queries
- **@media (max-width: 1200px)**:
  - `max-width: 100%;`: Allows the container to expand fully on smaller screens.

- **@media (max-width: 768px)**:
  - `padding: 15px;`: Reduces padding for medium-sized screens.

- **@media (max-width: 480px)**:
  - `padding: 10px;`: Further reduces padding for small screens.

## Usage Examples

```html
<!-- Example of a main content container with default styling -->
<div class="container bg-main-content">
    <!-- Content goes here -->
</div>

<!-- Example of a container with a highlight background -->
<div class="container bg-highlight">
    <!-- Highlighted content goes here -->
</div>

<!-- Example of a sidebar layout -->
<div class="container-sidebar">
    <div class="main-content">
        <!-- Main content goes here -->
    </div>
    <div class="sidebar">
        <!-- Sidebar content goes here -->
    </div>
</div>
```
