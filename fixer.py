import os

def resolve_conflict_in_file(file_path):
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            lines = file.readlines()

        resolved_lines = []
        inside_conflict = False

        for line in lines:
            if line.startswith('<<<<<<<'):
                inside_conflict = True
                continue
            elif line.startswith('======='):
                continue
            elif line.startswith('>>>>>>>'):
                inside_conflict = False
                continue
            
            if not inside_conflict:
                resolved_lines.append(line)

        with open(file_path, 'w') as file:
            file.writelines(resolved_lines)

        print(f"Conflict resolved in {file_path}")
    except UnicodeDecodeError:
        print(f"Conflict could not be resolved in {file_path}")

def resolve_conflicts_in_directory(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == "fixer.py":
                continue

            file_path = os.path.join(dirpath, filename)
            resolve_conflict_in_file(file_path)

# Example usage
root_directory = './'  # Replace with the path to the directory you want to check
resolve_conflicts_in_directory(root_directory)
