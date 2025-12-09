import os

file_path = 'paper/access.tex'

with open(file_path, 'r') as f:
    content = f.read()

# Markers
appendices_start_marker = r'\appendices'
references_start_marker = r'%====================' + '\n' + r'% References'
eod_marker = r'\EOD'

# Find indices
try:
    appendices_idx = content.index(appendices_start_marker)
    references_idx = content.index(references_start_marker)
    eod_idx = content.index(eod_marker)
except ValueError as e:
    print(f"Error finding markers: {e}")
    exit(1)

print(f"Appendices start: {appendices_idx}")
print(f"References start: {references_idx}")
print(f"EOD start: {eod_idx}")

# Extract blocks
# Main text ends before appendices
main_text_part1 = content[:appendices_idx]

# Appendix block is from \appendices up to References
appendix_block = content[appendices_idx:references_idx]

# References and Bios block is from References up to EOD
# Note: references_idx is where references start.
# eod_idx is where \EOD starts.
ref_and_bios_block = content[references_idx:eod_idx]

# End part is \EOD and rest
end_part = content[eod_idx:]

# Construct new content
# Order: Main Text -> References/Bios -> Appendices -> EOD/End
new_content = main_text_part1 + ref_and_bios_block + appendix_block + end_part

with open(file_path, 'w') as f:
    f.write(new_content)

print("Successfully moved appendices.")
