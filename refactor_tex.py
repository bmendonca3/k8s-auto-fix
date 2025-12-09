import re

def refactor_tex():
    with open('paper/access.tex', 'r') as f:
        content = f.read()

    # Define markers
    start_marker = r'\\appendices'
    end_marker = r'%====================\n% References'

    # Locate start
    start_match = re.search(start_marker, content)
    if not start_match:
        print("Error: Could not find start marker")
        return

    start_idx = start_match.start()

    # Locate end
    end_match = re.search(end_marker, content)
    if not end_match:
        print("Error: Could not find end marker")
        return

    end_idx = end_match.start()

    # Extract block
    # The block includes \appendices up to the end marker
    appendix_block = content[start_idx:end_idx]

    # Remove block from content
    # We remove from start_idx to end_idx
    new_content = content[:start_idx] + content[end_idx:]

    # Locate insertion point (after last \end{IEEEbiography})
    # We look for the last occurrence
    bio_end_marker = r'\\end{IEEEbiography}'
    bio_matches = list(re.finditer(bio_end_marker, new_content))

    if not bio_matches:
        print("Error: Could not find biography end marker")
        return

    last_bio_end = bio_matches[-1].end()

    # Check if \EOD is there
    eod_marker = r'\\EOD'
    eod_match = re.search(eod_marker, new_content[last_bio_end:])

    if not eod_match:
        print("Warning: Could not find EOD after biography, inserting anyway")

    # Process appendix block to add \clearpage
    # "Insert a \clearpage command immediately before each \section command."
    # We should skip the first one if we don't want a clearpage right after \appendices?
    # The instructions say:
    # "Inject Spacers: Within the newly pasted Appendices block, iterate through every instance of \section{...}."
    # "Apply Logic: Insert a \clearpage command immediately before each \section command."
    # Example: \clearpage \section{Grok/xAI Failure Analysis}

    # Let's do a substitution on the extracted block
    # We handle \section
    # But wait, \appendices is a command, usually followed by sections.
    # The ieeeaccess class might behave specifically.
    # The instruction is explicit: "Insert a \clearpage command immediately **before** each \section command."

    def clearpage_sub(match):
        return r'\clearpage ' + match.group(0)

    processed_block = re.sub(r'\\section\{', clearpage_sub, appendix_block)

    # Insert block
    # We insert after last_bio_end
    # Ensure some newlines

    final_content = (
        new_content[:last_bio_end] +
        "\n\n" +
        processed_block +
        "\n" +
        new_content[last_bio_end:]
    )

    # Write back
    with open('paper/access.tex', 'w') as f:
        f.write(final_content)

    print("Refactoring complete.")

if __name__ == "__main__":
    refactor_tex()
