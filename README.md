# RADAR BF 2026 — Sistema Inteligente de Monitoramento de Ofertas

Plataforma completa de inteligência de mercado, monitoramento automático, histórico estatístico e detecção de falsos descontos desenvolvida para identificar o melhor momento de compra do **Sony PlayStation 5 Slim Digital Edition** e do controle **Sony DualSense** adicional durante a **Black Friday 2026**.

---

## 1. Visão Geral das Funcionalidades Implementadas

1. **Produtos Monitorados com Separação Estrita de Versões (Seção 2)**:
   - **Produto A (Prioritário)**: *Sony PlayStation 5 Slim Digital Edition (1TB)*, Bundles oficiais com jogos e Bundles com 2º controle DualSense, identificando revisões de hardware (`CFI-2014B`, `CFI-2015B`), nacionalidade Anatel e garantia oficial Sony Brasil.
   - **Isolamento Estrito**: *PS5 Fat (825GB)*, *PS5 Pro (2TB)* e *PS5 Slim com Leitor de Disco* são classificados automaticamente na **Área de Oportunidades Alternativas**, jamais poluindo o menor preço ou a média do PS5 Slim Digital.
   - **Produto B (Prioritário)**: *Controle Sem Fio Sony DualSense Oficial* (Branco, Midnight Black, Cosmic Red, Starlight Blue, Galactic Purple, Grey Camouflage, Cobalt Blue, Sterling Silver, Chroma e Edições Especiais), estritamente separado de controles paralelos/similares.

2. **Módulos Independentes por Loja e Fonte (Seção 3)**:
   - Conectores individuais em `backend/collectors/` para: **Amazon Brasil**, **Mercado Livre**, **KaBuM!**, **Magazine Luiza**, **Fast Shop**, **Casas Bahia**, **Ponto**, **Carrefour**, **Promobit** e **Pelando**.
   - Conformidade rigorosa: consulta APIs públicas (ex: API Oficial MLB, VTEX Intelligent Search público, JSON-LD / NextData) e nunca tenta contornar CAPTCHAs ou bloqueios WAF/Cloudflare. Quando uma loja exige credencial de API oficial de parceiro ou bloqueia acesso automatizado anônimo, o sistema informa o status com transparência e exibe o guia de configuração da API sem jamais inventar preços.

3. **Monitoramento Automático Independente do Frontend (Seção 5)**:
   - Agendador configurável via `APScheduler` em `backend/scheduler/radar_scheduler.py` rodando continuamente junto ao backend:
     - **Período Normal**: a cada 30 minutos.
     - **Período de Alta Atividade (Black Friday)**: a cada 10 minutos.
     - **Período Noturno (00h–06h)**: a cada 60 minutos.

4. **Histórico Imutável e Estatística Descritiva (Seção 6)**:
   - Filtros para **24 horas, 7 dias, 30 dias, 90 dias e Histórico Completo**.
   - Cálculos exatos de **Menor preço, Maior preço, Média, Mediana, Desvio Padrão, Variação Percentual, Frequência de Quedas e Frequência de Aumentos**, diferenciando PIX/à vista, Cartão parcelado, Cupons e Frete.

5. **Inteligência do Radar (Índice 0–100) & Detecção de Falsos Descontos (Seções 7 e 10)**:
   - Índice de Oportunidade auditável de **0 a 100** calculado sobre 10 fatores estatísticos.
   - Trava de segurança: ofertas sem histórico suficiente (`< 3` coletas) têm pontuação máxima limitada a 55.
   - **Detector de Falsos Descontos ("Metade do Dobro")**: identifica aumentos recentes pré-promoção, preços "promocionais" acima da média de 30 dias e preços de referência ("De:") inflados.

6. **Previsão de Mercado e Melhores Horários (Seções 8 e 9)**:
   - Previsões para **24 horas, 3 dias e 7 dias** usando Médias Móveis (7d/30d), Regressão Linear Amortecida (OLS) e Volatilidade, com aviso explícito quando não há dados suficientes.
   - Análise de **Melhores Horários** agrupada por hora do dia, dia da semana, dia do mês e semana de novembro (Black Friday), ponderando qualidade real vs quantidade de consultas realizadas.

7. **Central de Alertas Internos, Relatórios e Configurações (Seções 11, 12 e 13)**:
   - Notificações 100% internas no dashboard (com opção de Web Notifications nativas do navegador).
   - Orçamento flexível: permite deixar os preços-alvo em branco para recomendação 100% guiada pelo histórico, além do indicador **"Vale a pena comprar agora?"**.
   - Relatórios executivos **Diário e Semanal** e **Backup Automático do SQLite**.

---

## 2. Estrutura do Projeto

```text
Bot ps5/
├── backend/
│   ├── main.py                  # Servidor FastAPI + Lifespan do Agendador Automático
│   ├── database.py              # Engine SQLite (WAL mode) / Pronto para PostgreSQL
│   ├── models/
│   │   ├── models.py            # 9 Tabelas ORM: products, stores, offers, price_history, alerts, monitoring_logs, coupons, settings, prediction_results
│   │   └── schemas.py           # Validação Pydantic
│   ├── collectors/
│   │   ├── base.py              # Classe base modular de coleta
│   │   ├── classifier.py        # Classificador PS5 Slim Digital vs Fat/Pro/Disco e DualSense Oficial vs Paralelo
│   │   ├── mercadolivre.py      # Conector Mercado Livre (API Oficial / Catálogo Público)
│   │   ├── retail_stores.py     # Conectores Amazon, KaBuM!, Magalu, Fast Shop, Casas Bahia, Ponto, Carrefour
│   │   ├── community_sources.py # Conectores Promobit e Pelando
│   │   └── registry.py          # Registro plugável de coletores
│   ├── analytics/
│   │   ├── statistics.py        # Média, mediana, desvio padrão, variação e frequências
│   │   ├── intelligence.py      # Índice de Oportunidade (0-100) e 10 fatores
│   │   ├── fake_discount.py     # Detecção de falsos descontos ("metade do dobro")
│   │   ├── predictions.py       # Previsão 24h, 3d e 7d (Médias Móveis + Regressão OLS)
│   │   ├── best_times.py        # Análise normalizada de melhores horários
│   │   └── reports.py           # Relatórios Diário e Semanal
│   ├── services/
│   │   ├── monitoring_service.py # Orquestração de coleta, histórico e catálogo
│   │   ├── alert_service.py     # Central de alertas internos
│   │   └── backup_service.py    # Backup consistente do banco SQLite
│   ├── scheduler/
│   │   └── radar_scheduler.py   # Agendador automático configurável (30m / 10m / Noturno)
│   ├── routes/
│   │   └── api_routes.py        # Endpoints REST das 10 páginas
│   └── tests/
│       └── test_radar_bf2026.py # Suíte de testes automatizados (Pytest)
├── frontend/
│   ├── src/
│   │   ├── components/          # Layout financeiro Dark/Green e navegação
│   │   ├── pages/               # As 10 páginas interativas completas
│   │   ├── charts/              # Gráficos interativos Recharts
│   │   ├── services/            # Cliente REST e formatadores America/Sao_Paulo
│   │   ├── hooks/               # Hook opcional de notificações do navegador
│   │   └── styles/              # Tailwind CSS
├── requirements.txt
├── .env.example
├── iniciar_radar.ps1
└── README.md
```

---

## 3. Como Executar o Sistema

### Opção 1 — Inicialização Automática com 1 Comando (PowerShell)

Na pasta raiz do projeto (`c:\Users\suporte.TECHCD\Documents\Bot ps5`), execute:

```powershell
.\iniciar_radar.ps1
```

Isso iniciará automaticamente:
- **Backend FastAPI + Monitoramento Automático**: `http://127.0.0.1:8000` (Documentação interativa Swagger em `http://127.0.0.1:8000/docs`)
- **Frontend React Interativo**: `http://localhost:5173`

---

### Opção 2 — Execução Manual em Dois Terminais

#### Terminal 1 — Backend e Agendador Automático:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal 2 — Frontend Interativo:
```powershell
cd frontend
npm run dev
```

---

## 4. Como Controlar o Monitoramento Automático

1. **Início Automático**: Assim que o backend é iniciado (`uvicorn backend.main:app`), o agendador entra em execução automaticamente (`SCHEDULER_AUTO_START=true`) no modo configurado e cria um backup automático do banco SQLite.
2. **Alteração de Frequência pela Interface**:
   - Acesse a página **10. Configurações** no menu lateral.
   - Escolha entre **Período Normal (30 min)**, **Alta Atividade Black Friday (10 min)** ou **Modo Noturno (60 min)** e clique em **Salvar Configurações**. O agendador aplica o novo intervalo imediatamente sem precisar reiniciar o servidor.
3. **Disparo Imediato**:
   - Clique no botão verde **"ATUALIZAR PREÇOS AGORA"** na barra lateral esquerda a qualquer momento para forçar uma varredura imediata em todas as fontes.

---

## 5. Como Executar os Testes Automatizados

Os testes utilizam banco de dados isolado em memória (`sqlite:///:memory:`), sem nunca misturar dados simulados de teste com o banco principal `radar_bf2026.db`:

```powershell
.\.venv\Scripts\pytest.exe backend/tests/test_radar_bf2026.py -v
```

---

## 6. Configuração Opcional de Credenciais de API Oficial (`.env`)

Se desejar habilitar acesso autenticado oficial para lojas que utilizam proteção anti-bot agressiva em buscas públicas, copie `.env.example` para `.env` e preencha:

- `MERCADOLIVRE_ACCESS_TOKEN`: Token OAuth do Mercado Livre Developers.
- `AMAZON_PAAPI_ACCESS_KEY`, `AMAZON_PAAPI_SECRET_KEY`, `AMAZON_PAAPI_PARTNER_TAG`: Chaves da Amazon Product Advertising API 5.0.
- `LOMADEE_APP_TOKEN`, `LOMADEE_SOURCE_ID`: Chaves da API de afiliados Lomadee (KaBuM!, Casas Bahia, Ponto).
- `DATABASE_URL`: String de conexão SQLAlchemy (padrão SQLite local; pode ser alterada para `postgresql+psycopg2://...` para migração imediata para PostgreSQL).
