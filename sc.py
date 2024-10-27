import os

def generate_project_structure_md(directory, level=0):
    md_content = ""
    for root, dirs, files in os.walk(directory):
        if level == 0:
            md_content += f"# {os.path.basename(root)}\n\n"
        else:
            md_content += f"{'  ' * (level - 1)}- {os.path.basename(root)}/\n"

        for file in files:
            md_content += f"{'  ' * level}- {file}\n"

        for dir in dirs:
            md_content += generate_project_structure_md(os.path.join(root, dir), level + 1)

    return md_content

# Укажите путь к корневой директории вашего проекта
project_directory = r"C:\Users\Den\Desktop\Work_Code\TRADEBOT\Traderbot\trading_bot"

# Генерация файла Markdown
md_file = "project_structure.md"
with open(md_file, "w") as file:
    file.write(generate_project_structure_md(project_directory))

print(f"Файл {md_file} успешно создан.")