REM installed on nssm on brisk2
uvicorn general_config_server:app --host=0.0.0.0 --port=8002 --log-level info > general_config_server.log 2>&1