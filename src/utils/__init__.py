"""Share file reading/writing, content hashes and evidence checks across pipeline stages.

``io`` handles stored mappings, ``reproducibility`` records run identity,
``frozen_evidence`` binds historical inputs to Git, and ``posthoc_evidence``
checks the separately labelled sampler-sensitivity artefacts.
"""
