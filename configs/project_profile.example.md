# Project Profile Example

Use this file to describe your research context for `generate-note-from-evidence-bank`.

Example:

```text
I am studying logistics package surface defect detection. I care about defect categories such as holes, wet damage, and scratches, but generated notes must not assume these are the source paper's original labels unless the paper states so. I want literature notes that support background, related work, method design, data augmentation discussion, and experiment comparison.
```

Copy this file locally and pass it with:

```powershell
python -m litflow.cli generate-note-from-evidence-bank `
  --research-context-file ".\configs\project_profile.example.md" `
  ...
```
