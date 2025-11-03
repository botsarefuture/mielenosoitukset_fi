## **Mielenosoitukset.fi Code Style Guide**

### **1. General Guidelines**
- **Python Version:** Use Python 3.9+.
- **Code Readability:** Prioritize readability over cleverness.
- **DRY Principle:** Avoid code duplication by reusing logic and components.
- **Error Handling:** Catch exceptions thoughtfully, and avoid generic `except:` clauses.

### **2. Naming Conventions**
- **Classes:** Use `PascalCase` for class names (e.g., `Organizer`, `Demonstration`).
- **Variables & Methods:** Use `snake_case` for variables and method names (e.g., `organization_id`, `fetch_organization_details`).
- **Constants:** Use `UPPER_CASE` for constants (e.g., `DAY_NAME_TO_NUM`).
- **Private Methods:** Prefix private methods and variables with an underscore (e.g., `_validate_fields`).

### **3. Documentation**
- **Docstrings:** Use **PEP 257** conventions for docstrings. Provide a short description of the class or function, followed by explanations of arguments and return values (if applicable).
  - Example for functions:
    ```python
    def fetch_organization_details(self):
        """
        Fetch the organization details from the database.

        Returns:
            dict: Organization details if found, None otherwise.
        """
    ```
  
### **4. Import Structure**
- **Order:** Follow this import order:
  1. Standard Library imports
  2. Third-party imports
  3. Local imports (e.g., `from mielenosoitukset_fi.database_manager import DatabaseManager`)
- **Avoid Wildcard Imports:** Always import specific modules or components (e.g., `from bson.objectid import ObjectId`).

### **5. Indentation & Spacing**
- **Indentation:** Use 4 spaces per indentation level.
- **Line Length:** Limit all lines to a maximum of 79 characters.
- **Blank Lines:** Use two blank lines between top-level functions and class definitions. Use one blank line between methods within a class.

### **6. Function & Method Design**
- **Small Functions:** Keep functions and methods small and focused. If a function does more than one thing, consider refactoring it.
- **Positional & Keyword Arguments:** Use keyword arguments where appropriate to improve code readability and prevent potential bugs.

### **7. Error Handling**
- **Try/Except Blocks:** Always catch specific exceptions rather than using a generic `Exception` class. Log error messages for easier debugging.
  - Example:
    ```python
    try:
        # code logic
    except ValueError as e:
        print(f"Invalid input: {e}")
    ```

### **8. Data Handling**
- **Use Data Models:** When dealing with MongoDB or similar databases, represent collections using classes and convert data between dicts and objects (e.g., `to_dict()` and `from_dict()` methods).
  
### **9. Class Design**
- **Constructor Arguments:** Default mutable arguments like lists or dictionaries should use `None` and initialize within the method body to avoid shared mutable states.
  - Example:
    ```python
    def __init__(self, social_media=None):
        self.social_media = social_media if social_media is not None else {}
    ```

### **10. Version Control**
- **Commit Messages:** Write clear, concise commit messages. Follow this format:
  - **Short Summary (50 characters or less)**
  - Detailed explanation of the changes (if necessary).
