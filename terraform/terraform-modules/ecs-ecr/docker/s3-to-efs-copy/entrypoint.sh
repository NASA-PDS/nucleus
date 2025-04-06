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


# Check the user or role that made the call
aws sts get-caller-identity

# Read values from command line arguments

EFS_CONFIG_DIR=$1
OPERATION=$2
HOT_ARCHIVE_S3_BUCKET_NAME=$3
COLD_ARCHIVE_S3_BUCKET_NAME=$4

if [ "$OPERATION" = "DELETE" ]
then

  filename="$EFS_CONFIG_DIR"/files_created.txt
  echo "Removing data files listed in $filename"

  while read -r line; do
      file_to_delete="$line"
      echo "Deleting- $file_to_delete"
      rm "$file_to_delete"
  done < "$filename"

fi

if [ "$OPERATION" = "COPY" ]
then

  echo "Copying data files listed in $EFS_CONFIG_DIR/data_file_list.txt from staging S3 to EFS"
  filename=$EFS_CONFIG_DIR/data_file_list.txt
  while read -r line; do
      s3_url_of_file="$line"
      echo "Name read from file - $s3_url_of_file"
      staging_bucket_name="s3://"
      hot_archive_bucket_name="/mnt/data/"
      hot_archive_target_location="${s3_url_of_file//$staging_bucket_name/$hot_archive_bucket_name}"
      aws s3 cp "$s3_url_of_file" "$hot_archive_target_location"
      echo "$hot_archive_target_location" >> "$EFS_CONFIG_DIR"/files_created.txt

      # Extract .fz files
      if [[ $hot_archive_target_location == *.fz ]]
      then
        echo "Extracting $hot_archive_target_location..."
        extracted_file_name=${hot_archive_target_location%.*}

        if [ -f "$extracted_file_name" ] ; then
            rm "$extracted_file_name"
        fi

        funpack -v "$hot_archive_target_location"
        echo "$extracted_file_name" >> "$EFS_CONFIG_DIR"/files_created.txt
      fi

  done < "$filename"

fi


if [ "$OPERATION" = "ARCHIVE" ]
then

  echo "Archiving data files listed in $EFS_CONFIG_DIR/data_file_list.txt from staging S3 to archive"
  filename=$EFS_CONFIG_DIR/data_file_list.txt
  while read -r line; do
      s3_url_of_file="$line"
      echo "Name read from file - $s3_url_of_file"
      staging_bucket_name="s3://$STAGING_S3_BUCKET_NAME/"

      hot_archive_bucket_name="s3://$HOT_ARCHIVE_S3_BUCKET_NAME/"
      hot_archive_target_location="${s3_url_of_file//$staging_bucket_name/$hot_archive_bucket_name}"
      echo "Archiving files to hot archive: $hot_archive_target_location"
      aws s3 cp "$s3_url_of_file" "$hot_archive_target_location"

      # Archiving files to hot archive will also add files to cold archive with the help of S3 replication

  done < "$filename"

fi

