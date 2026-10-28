"""LaTeX writing: compile a document, read its log, check its sources and map between the
sources and the PDF. Shared by the agent's LaTeX tools and the desktop's TeX editor.

The log parser, the source rules, the SyncTeX search and the starter documents follow TeXButler
(MIT, Copyright 2026 WhitePepperLambSoup), rewritten in Python.
"""
