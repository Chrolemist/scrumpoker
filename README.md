# Scrum Poker (Streamlit)

En enkel interaktiv Scrum Poker-app byggd med Streamlit. Stöd för flera användare (samma körning), rums-ID, timer, användarberättelse och röstning med:
- T‑shirt-läge (XS,S,M,L,XL) utan poäng – visar enbart valda etiketter
- Poängläge med dynamiskt anpassat poängsystem (lägg till/ta bort kort)

## Funktioner
- Skapa eller gå med i rum via kod
- Ange eget visningsnamn
- Skriv in användarberättelse som estimeras
- Välj skala: T‑shirt (etiketter) eller Poäng (egna kort)
- Lägg till egna poängkort med "+" och spara
- Starta timer (facilitator) och visa nedräkning
- Auto-uppdatering för alla klienter (ingen manuell refresh)
- Rösta anonymt tills reveal
- Kort med mörkt tema, hover-effekter och flip-animation vid reveal
- Statistik vid reveal (medel/std i poängläge, frekvenser i T‑shirt-läge)

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
Appen använder en enkel JSON-fil (`rooms_state.json`) för state. Vid omstart förloras data och samtidiga skrivningar hanteras enkelt med lås men utan transaktioner. För robust multi-user persistens och realtid rekommenderas Redis/DB + websockets.

## Anpassningar
- Ändra tema i `.streamlit/config.toml`
- Lägg till fler skalor eller värden i sidopanelen.

