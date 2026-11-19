#!/bin/bash
# Copyright 2024, California Institute of Technology ("Caltech").
# U.S. Government sponsorship acknowledged.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
# * Neither the name of Caltech nor its operating division, the Jet Propulsion
# Laboratory, nor the names of its contributors may be used to endorse or
# promote products derived from this software without specific prior written
# permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Fetches Amazon Inspector (ECR enhanced scanning) findings for every
# Nucleus-owned ECR repository and writes one JSON report per repository
# (per profile, if profiles are used) to ./ecr-scan-reports/.
#
# IMPORTANT: this uses `aws inspector2 list-findings`, not
# `aws ecr describe-image-scan-findings`. The latter only queries ECR's
# legacy "basic scanning" (Clair-based) results and silently misses
# everything Inspector (ECR "enhanced scanning") finds -- on this project
# that was the difference between "0 findings" and 89 real findings
# (27 High) for pds-nucleus-config-init alone. Only use this script if
# enhanced scanning is actually enabled on these repos; if it isn't,
# list-findings will just come back empty for a different reason (no
# Inspector coverage at all, not "nothing found").
#
# Only ACTIVE findings are fetched -- SUPPRESSED/CLOSED findings are
# excluded, since those are already accepted-risk or resolved.
#
# Usage:
#   ./get-ecr-scan-findings.sh                        # current AWS CLI credentials
#   ./get-ecr-scan-findings.sh -r us-east-1            # a different region
#   ./get-ecr-scan-findings.sh -p "cds-dev cds-test cds-prod"   # one or more AWS CLI profiles
#
# Repository list below must be kept in sync with the aws_ecr_repository
# resources in terraform/terraform-modules/ecs-ecr/ecs_ecr.tf.

set -euo pipefail

REGION="us-west-2"
PROFILES=""
OUTPUT_DIR="ecr-scan-reports"

REPOS="pds-nucleus-config-init pds-nucleus-s3-to-efs-copy pds-registry-loader-harvest pds-validate pds-nucleus-tools-java"

while getopts "r:p:o:h" opt; do
  case "$opt" in
    r) REGION="$OPTARG" ;;
    p) PROFILES="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    h)
      echo "Usage: $0 [-r region] [-p \"profile1 profile2 ...\"] [-o output-dir]"
      exit 0
      ;;
    *)
      echo "Unknown option" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

fetch_one() {
  local repo="$1"
  local profile_args=()
  local file_prefix=""

  if [[ -n "${2:-}" ]]; then
    profile_args=(--profile "$2")
    file_prefix="${2}-"
  fi

  echo "Fetching Inspector findings for ${repo}${2:+ (profile: $2)}..."

  # Resolve the digest that "latest" actually points at right now, via ECR
  # directly, and filter Inspector findings by that digest instead of by
  # the "latest" tag. Inspector's own tag-to-digest index can lag behind a
  # fresh push/retag by ECR -- confirmed: right after pushing a new image,
  # `ecrImageTags: latest` kept returning the *previous* digest's findings
  # for a while, even though `describe-image-scan-findings` already showed
  # the new digest's scan as COMPLETE. Filtering by digest is immediate
  # and authoritative, matching what the Inspector console shows when you
  # navigate to that digest directly.
  local digest
  digest=$(aws ecr describe-images \
      --repository-name "$repo" \
      --region "$REGION" \
      "${profile_args[@]}" \
      --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageDigest' \
      --output text 2>/dev/null) || digest=""

  local filter
  if [[ -n "$digest" && "$digest" != "None" ]]; then
    filter=$(cat <<JSON
{
  "ecrImageRepositoryName": [{"comparison": "EQUALS", "value": "$repo"}],
  "ecrImageHash": [{"comparison": "EQUALS", "value": "$digest"}],
  "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}]
}
JSON
)
  else
    echo "  WARNING: couldn't resolve latest digest for $repo, falling back to tag filter" >&2
    filter=$(cat <<JSON
{
  "ecrImageRepositoryName": [{"comparison": "EQUALS", "value": "$repo"}],
  "ecrImageTags": [{"comparison": "EQUALS", "value": "latest"}],
  "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}]
}
JSON
)
  fi

  if ! aws inspector2 list-findings \
      --filter-criteria "$filter" \
      --region "$REGION" \
      "${profile_args[@]}" \
      --output json > "${OUTPUT_DIR}/${file_prefix}${repo}-scan-report.json"; then
    echo "  FAILED for $repo${2:+ (profile: $2)} (Inspector not enabled, no access, or API error)" >&2
  fi
}

if [[ -z "$PROFILES" ]]; then
  for repo in $REPOS; do
    fetch_one "$repo"
  done
else
  for profile in $PROFILES; do
    for repo in $REPOS; do
      fetch_one "$repo" "$profile"
    done
  done
fi

echo "Done. Reports written to ${OUTPUT_DIR}/"
