
def collect_tags(request):
    """
    Collect tags data from the request form.

    This function extracts multiple tags from the form fields and returns them as a list.

    Args:
        request: The incoming request object containing form data.

    Returns:
        list: A list of tags extracted from the form.
    """
    tags = []
    i = 1

    while True:
        # Extract the tag value from the dynamic form field names
        tag_name = request.form.get(f"tag_{i}")

        # Break the loop if no tag name is found
        if not tag_name:
            if not request.form.get(f"tag_{i+1}"):
                break
            
            else:
                continue
            
        # Append the trimmed tag to the list
        tags.append(tag_name.strip())

        i += 1  # Move to the next tag field

    return tags