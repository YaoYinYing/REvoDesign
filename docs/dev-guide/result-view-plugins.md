# Result Storyboards and File Viewers

Runner owns meaning. Server owns files. Expected File Tree connects them.

```text
runner output -> ExpectedFileTree -> ResultContext -> ResultStoryboard
                                      |                 |
                                      +--> FileViewer <--+
```

`ExpectedFileTree` lives with a runner and gives each approved output a logical
identity. `ResultContext` exposes only those resolved, manifest-approved files.
`ResultStoryboard` is trusted local browser code owned by that runner and
explains the scientific result. `FileViewer` is server-owned, format-specific
presentation (structure, table, text, image, or download) with no knowledge of
the scientific program that created a file.

## Add a runner storyboard

Place `expected_files.yaml` and `storyboard/` beside the runner's Dockerfile.
The file contract uses a logical identifier, path or pattern, `required`, and
`cardinality` (`one` or `many`). Declare a local `./index.js` in
`storyboard/storyboard.yaml`, including its required and optional logical file
identifiers. The server validates containment and declarations at publication;
the browser receives no filesystem paths and dynamically loads only this local,
authenticated asset. Storyboard code uses `context.files.get("identifier")`
and delegates compatible files through `context.services.openFile(file)`.

No remote URLs, YAML JavaScript, task-output JavaScript, filesystem discovery,
or task-name switches are permitted. Missing optional files return no value;
missing required files are explicit output-check failures. If a storyboard or a
file preview fails, the scientific status plus Files & diagnostics/downloads
remain available.

The old `result_workspace` protocol remains a migration-only generic view
mechanism for runners not yet migrated. New task-specific scientific composition
must be runner-owned rather than added to that central taxonomy.
