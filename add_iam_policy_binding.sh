#!/bin/bash
ORG_ID=740428501219
USER_EMAIL=themintyfresh1999@gmail.com

gcloud organizations add-iam-policy-binding "$ORG_ID" \
  --member="user:$USER_EMAIL" \
  --role="roles/orgpolicy.policyAdmin"
