# Scrum Poker (Streamlit)

En enkel interaktiv Scrum Poker-app byggd med Streamlit. Stöd för flera användare (samma körning), rums-ID, timer, användarberättelse och röstning med skalor (XS,S,M,L,XL) inklusive egna tids-/poängvärden.

## Funktioner
- Skapa eller gå med i rum via kod
- Ange eget visningsnamn
- Skriv in användarberättelse som estimeras
- Välj röstningsskala och egna värden
- Starta timer (facilitator) och visa nedräkning
- Rösta anonymt tills reveal
- Kort med mörkt tema, hover-effekter och flip-animation vid reveal
- Automatisk sammanställning (medel, spridning, konsensusdetektion)

## Kör lokalt
```powershell
pip install -r requirements.txt
streamlit run app.py
```
Öppna sedan URL:en som skrivs ut (oftast http://localhost:8501).

## Deploy (Streamlit Community Cloud)
1. Skapa ett nytt publikt repo med dessa filer.
2. Gå till https://share.streamlit.io och koppla repo.
3. Ange `app.py` som huvudfil.

## Begränsningar
Appen använder minne på servern för state. Vid omstart förloras data. För mer robust multi-user persistens kan du koppla databas eller Redis.

## Anpassningar
- Ändra tema i `.streamlit/config.toml`
- Lägg till fler skalor eller värden i sidopanelen.

