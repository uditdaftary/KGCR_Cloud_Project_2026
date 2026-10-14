"""The gold set: hand-authored reference configurations, never trained on (FD-05 4C).

Nothing in the corpus, defect, recommender, reconstruction or advisor packages may import
this package; a test enforces it, because contaminating the gold set destroys both its
jobs (the regression gate and the false-positive baseline) irrecoverably.
"""
