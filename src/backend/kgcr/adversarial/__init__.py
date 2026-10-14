"""Corpus D (FD-05 4D): independently authored, deliberately vulnerable Terraform.

TerraGoat and CloudGoat were written by someone else, so recall against them is evidence
that self-injected defects cannot give. The repositories are cloned read-only and parsed,
never executed and never ``terraform init``ed. Their licences are read from the repositories
themselves and checked against the accepted list before anything is counted.
"""
