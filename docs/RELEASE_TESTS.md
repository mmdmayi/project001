# FaceInverse 0.3.0 verification

Date: 2026-10-27. Target: Windows x64 / Maya 2024.

- 28 numerical tests passed: baseline inverse solving, expression-space propagation, local corrections, exact key constraints, channel masks, bounds, missing detections, conflicts, persistence, library compatibility and relocation.
- Actual Qt capture / toggle / solve button tests passed in Maya 2024 offscreen mode.
- Three authored pose fixtures, 180 controller constraints: after saving and reopening the real MetaHuman scene, controller error = 0 and sampled Mesh coordinate error = 0 cm.
- The pose fixtures are scripted authoring tests, not independently labelled video ground truth.
- A private Python 3.12.10 environment installed from offline wheels in a clean Chinese / space-containing path; imports, model initialization and all 28 tests passed.
- A separate initially empty online package installed all dependencies and passed all 28 tests.
- The relocated installed runtime prepared a real 30-frame actor project from a Chinese video filename, generated audio and initial animation, then recalculated and baked an authored key pose.
- Earlier video baseline tests cover four clips / 1162 frames / 60 Faceboard controls. Those results do not prove commercial-product-level reconstruction accuracy.

The package implements animator-authored expression keyframes and expression-based recalculation. It does not claim to reproduce Faceware/Facegood proprietary algorithms, and tests on one machine in isolated environments do not constitute testing on every other computer or GPU.

Maya, the character, DNA and Epic plugins are not distributed. Offline installation requires the model already present in models/face_landmarker.task; the online installer downloads the fixed, hash-verified model from Google's official URL.

Chinese installation and usage instructions: PACKAGE_INSTALL_CN.md and USER_GUIDE_CN.md.

A nondeforming rig with changing diagnostic attributes was explicitly rejected by the Maya worker.
