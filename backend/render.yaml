services:
  - type: web
    name: options-bot-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: APP_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
      - key: ALLOWED_ORIGINS
        value: '["https://your-frontend.vercel.app"]'
      - key: DEFAULT_SYMBOL
        value: NIFTY
      - key: DEFAULT_CAPITAL
        value: "100000"
    healthCheckPath: /health
    autoDeploy: true
