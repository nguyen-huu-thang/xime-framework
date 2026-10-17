The first Windows artifact check rejected the existing .gitignore member of the sdist.
Hatchling includes this VCS ignore file; it is present in the earlier Linux artifact too.
The diagnostic allowlist was corrected to permit this exact filename and still compare
its bytes with the checkout. No framework packaging rule or source was changed to pass.
Build, twine, lint/type, tests, docs and advisory checks had already completed successfully;
only artifact inspection and the fresh wheel runtime continued with --artifact-only.
