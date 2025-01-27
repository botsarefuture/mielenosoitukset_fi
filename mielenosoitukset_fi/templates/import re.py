import re
import os
import shutil

def replace_hyphens_in_vars(css_content):
    """
    Replace hyphens with underscores in CSS variable names.

    Parameters
    ----------
    css_content : str
        The original CSS content.

    Returns
    -------
    str
        The modified CSS content with underscores in variable names.
    """
    pattern = r'--([a-zA-Z0-9_-]+)'
    replaced_content = re.sub(pattern, lambda match: f'--{match.group(1).replace("-", "_")}', css_content)
    return replaced_content

def main():
    """
    Main function to walk through /static/css/, replace hyphens with underscores in CSS variable names, back up original files, and write changes.
    """
    for root, dirs, files in os.walk('/home/verso/Desktop/mosoitukset_fi_v3/mielenosoitukset_fi/mielenosoitukset_fi/templates'):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                shutil.copy(filepath, f"{filepath}.bak")
                with open(filepath, 'r') as file:
                    css = file.read()
                modified_css = replace_hyphens_in_vars(css)
                with open(filepath, 'w') as file:
                    file.write(modified_css)

if __name__ == "__main__":
    main()
