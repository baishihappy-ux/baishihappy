# Visible Brand Name Neutralization

## Scope

- Removed the former Chinese and English product name from customer-visible window titles, authorization text, navigation labels, runtime-board text, and ship annotation.
- Kept the black/gold space design, bronze-vessel logo, bronze-vessel spacecraft, background audio, version number, and runtime behavior unchanged.
- Kept compatibility-sensitive environment variables, renderer bridge identifiers, executable names, authorization-code format, and Windows DPAPI entropy unchanged.

## Recovery

- The GitHub project remains the sole disaster-recovery source.
- The only formal recovery entry remains `Code` -> `Download ZIP` -> a new empty folder -> root `恢复生产环境.cmd`.
- No installer or formal customer package is created by this change.
