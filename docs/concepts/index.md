# Concepts

The domain ideas behind portable-python. Read these to understand *why* the build works the way it does.

* [Portability](/concepts/portability.md) - What "portable" means here, and how it is validated.
* [Static linking](/concepts/static-linking.md) - Why dependencies are compiled statically and paths relativized.
* [Telltale detection](/concepts/telltale-detection.md) - How the tool decides whether a library must be compiled or already exists.
* [Folder masking](/concepts/folder-masking.md) - The macOS `/usr/local` RAM-disk mask that prevents accidental dynamic linking.
* [Build layout](/concepts/build-layout.md) - The `build/` and `dist/` folder structure shared by every component.
