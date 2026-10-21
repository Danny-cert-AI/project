  
# Milestone 2

## Updates to Milestone 1 based on feedback.
  

 1. It was pointed out that requirements.txt looks suspiciously short and without version numbers (reducing reproducibility). I therefore pinned the dependencies in this commit: 85babfb Pin direct dependencies and add requirements.lock
 2. To save space in BigQuerry, you could use an ID based solution or views, instead of creating separate large tables (duplicating a lot of data)
 3. Feedback observed that raw data could be compressed to avoid having many csv files.
I gzipped each csv file using gzip (gzip -n datasets/raw/*.csv) Csv files are just ascii text so the compression achieved a 92% reduction (checked with the -l param gzip  -l  datasets/raw/*.csv.gz) .BigQuery supports gzipped files and decompresses as it loads.
 4. Attibution . I updated the attribution in Milestone1. 7e07b6a
