import re
import sys
import os

def Invoke(*args, **kwargs):
    try:
        # Extract the markdown content from the arguments
        markdown_content = args[0] if args else kwargs.get('content', '')
        
        # Extract the title from the markdown content
        title_line = markdown_content.splitlines()[0]
        if not title_line.startswith('# '):
            return "False"
        
        # Use the title as the filename, removing the markdown header
        # Sanitize the filename to remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', title_line[2:].strip()) + '.md'
        
        # Remove leading spaces from each line to fix markdown formatting
        formatted_content = '\n'.join(line.lstrip() for line in markdown_content.splitlines())
        
        # Determine the directory for saving the file
        summarizations_dir = os.getenv('SUMMARIZATIONS_DIR', os.path.join(os.getcwd(), 'Summarizations'))
        
        # Create the Summarizations directory if it doesn't exist
        os.makedirs(summarizations_dir, exist_ok=True)
        
        # Save the content to a markdown file in the Summarizations directory
        file_path = os.path.join(summarizations_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(formatted_content)
        
        return "True"
    except Exception as e:
        return "False"

if __name__ == "__main__":
    # Process input from command-line arguments
    if len(sys.argv) > 1:
        markdown_input = sys.argv[1]
        result = Invoke(markdown_input)
        print(result)
    else:
        print("False")