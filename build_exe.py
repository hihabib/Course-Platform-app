import os
import PyInstaller.__main__

script_name = "dev_server_ui.py"
icon_path = "icon.ico"  # Optional: include if you have an .ico file

# Ensure logs and UI assets are included (if any)
data_files = [
    "copy.png;.",  # include copy icon if available
]

# Build options
build_args = [
    "--name=Course Platform",
    "--onefile",
    "--noconsole",
]

# Add icon if it exists
if os.path.exists(icon_path):
    build_args.append(f"--icon={icon_path}")

# Include data files
for entry in data_files:
    if os.path.exists(entry.split(";")[0]):
        build_args.append(f"--add-data={entry}")

# Add the main script
build_args.append(script_name)

# Run PyInstaller
PyInstaller.__main__.run(build_args)
