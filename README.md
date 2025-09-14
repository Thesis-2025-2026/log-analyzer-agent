# 📊 Log Analyzer Agent

A lightweight anomaly detection pipeline for logs with AI-powered analysis.  
The system uses **Redis Pub/Sub** for real-time log streaming and **Postgres** for structured, queryable log storage.  
The AI Agent receives suspicious logs in real-time and can query Postgres for historical context.  

---

## 🚀 Architecture

- **Log Generator**: publishes synthetic logs to Redis & stores them in Postgres.  
- **Anomaly Detector**: subscribes to `logs`, flags anomalies, publishes to `anomalies`.  
- **AI Agent**: subscribes to `anomalies`, queries Postgres for related context.  
- **Postgres**: stores all logs (`level`, `timestamp`, `raw JSONB`).  
- **Redis**: lightweight message broker for real-time streaming.  

---

## ⚙️ Setup

1. **Start services (Redis + Postgres)**  
   docker compose up -d

   - Redis: localhost:6379  
   - Postgres: localhost:5433  

2. **Database schema**:
   (auto-loaded via `infra/init_db.sql`)

3. **Run components**  

   # Generate logs
   python log-generator/generator.py

   # Run detector
   python detector/detector.py

   # Run AI agent
   python agent/agent.py
