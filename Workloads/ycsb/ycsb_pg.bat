
.\bin\ycsb run jdbc -s -P workloads\workloada -P conf\db.properties -threads 50 -s >> logFile_PCC.txt
D:\PostgreSQL13\bin\pg_ctl.exe -D ../data -l logFile.txt stop