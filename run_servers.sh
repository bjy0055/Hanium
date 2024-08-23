#!/bin/bash

# Flask 서버 실행
cd flask_server
source myenv/bin/activate  # 가상환경 활성화
python app.py 

# Node.js 서버 실행
cd ../node_server
npm install
npm start
