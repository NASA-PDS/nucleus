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

set -euo pipefail

# Check the user or role that made the call
aws sts get-caller-identity

# Read values from command line arguments
EFS_CONFIG_DIR=$1
OPERATION=$2
HOT_ARCHIVE_S3_BUCKET_NAME=${3:-}   # only required for ARCHIVE

if [ "$OPERATION" = "DELETE" ]
then

  filename="$EFS_CONFIG_DIR/files_created.txt"

  if [ ! -f "$filename" ]; then
    echo "files_created.txt not found in $EFS_CONFIG_DIR — nothing to delete"
  else
    echo "Removing data files listed in $filename"
    while read -r line; do
        echo "Deleting: $line"
        rm -f "$line"   # -f: no error if already removed (handles retry duplicates)
    done < "$filename"
  fi

fi

if [ "$OPERATION" = "COPY" ]
then

  MAX_RETRIES=3
  RETRY_DELAY=5

  echo "Copying data files listed in $EFS_CONFIG_DIR/data_file_list.txt from staging S3 to EFS"
  filename=$EFS_CONFIG_DIR/data_file_list.txt
  while read -r line; do
      s3_url_of_file="$line"
      echo "Name read from file - $s3_url_of_file"
      efs_target_location="${s3_url_of_file/s3:\/\//\/mnt\/data\/}"
      mkdir -p "$(dirname "$efs_target_location")"

      # Retry each file up to MAX_RETRIES times before failing
      copied=false
      for attempt in $(seq 1 $MAX_RETRIES); do
          if aws s3 cp "$s3_url_of_file" "$efs_target_location"; then
              copied=true
              break
          fi
          echo "Attempt $attempt/$MAX_RETRIES failed for $s3_url_of_file — retrying in ${RETRY_DELAY}s..."
          sleep $RETRY_DELAY
      done

      if [ "$copied" = false ]; then
          echo "ERROR: Failed to copy $s3_url_of_file after $MAX_RETRIES attempts" >&2
          exit 1
      fi

      echo "$efs_target_location" >> "$EFS_CONFIG_DIR"/files_created.txt

      # Extract .fz files
      if [[ $efs_target_location == *.fz ]]
      then
        echo "Extracting $efs_target_location..."
        extracted_file_name="${efs_target_location%.*}"

        if [ -f "$extracted_file_name" ] ; then
            rm "$extracted_file_name"
        fi

        funpack -v "$efs_target_location"
        echo "$extracted_file_name" >> "$EFS_CONFIG_DIR"/files_created.txt
      fi

  done < "$filename"

fi


if [ "$OPERATION" = "ARCHIVE" ]
then

  if [ -z "$HOT_ARCHIVE_S3_BUCKET_NAME" ]; then
      echo "Error: HOT_ARCHIVE_S3_BUCKET_NAME (arg 3) is required for ARCHIVE operation" >&2
      exit 1
  fi

  MAX_RETRIES=3
  RETRY_DELAY=5

  echo "Archiving data files listed in $EFS_CONFIG_DIR/data_file_list.txt to s3://$HOT_ARCHIVE_S3_BUCKET_NAME"
  filename=$EFS_CONFIG_DIR/data_file_list.txt
  while read -r line; do
      s3_url_of_file="$line"
      echo "Archiving: $s3_url_of_file"

      # Extract the key path after the bucket name, then build the target URL.
      # e.g. s3://pds-img-staging/a/b/c.fits -> s3://hot-archive-bucket/a/b/c.fits
      s3_path="${s3_url_of_file#s3://}"         # pds-img-staging/a/b/c.fits
      s3_key="${s3_path#*/}"                     # a/b/c.fits
      hot_archive_target_location="s3://${HOT_ARCHIVE_S3_BUCKET_NAME}/${s3_key}"

      echo "Archiving to hot archive: $hot_archive_target_location"

      archived=false
      for attempt in $(seq 1 $MAX_RETRIES); do
          if aws s3 cp "$s3_url_of_file" "$hot_archive_target_location"; then
              archived=true
              break
          fi
          echo "Attempt $attempt/$MAX_RETRIES failed for $s3_url_of_file — retrying in ${RETRY_DELAY}s..."
          sleep $RETRY_DELAY
      done

      if [ "$archived" = false ]; then
          echo "ERROR: Failed to archive $s3_url_of_file after $MAX_RETRIES attempts" >&2
          exit 1
      fi

      # Archiving files to hot archive will also add files to cold archive with the help of S3 replication

  done < "$filename"

fi

if [[ "$OPERATION" != "COPY" && "$OPERATION" != "DELETE" && "$OPERATION" != "ARCHIVE" ]]; then
  echo "Error: unknown OPERATION '$OPERATION'. Expected COPY, DELETE, or ARCHIVE." >&2
  exit 1
fi
