#!/usr/bin/awk -f

# Step 1: Check if the line starts with '>', if yes, keep it, otherwise skip it.
/^>/ {
    # Step 2: Remove the heading '>'
    gsub(/^>/, "", $0)

    # Step 3: Find the index of '_cluster'
    idx_cluster = index($0, "_cluster")

    # Step 4: Extract the mutation info using substr function
    mutation_info = substr($0, 1, idx_cluster - 1)

    # Print the extracted mutation info
    print mutation_info
}
