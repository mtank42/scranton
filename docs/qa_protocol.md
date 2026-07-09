# Protocole QA — Scranton

> Doc opérateur, en français : c'est le script que suit le propriétaire.
> Trois niveaux : la non-régression automatisée (§4, exécutée par le
> mainteneur à chaque jalon), le protocole complet manuel (§2, avant
> une démo ou après un gros jalon), les protocoles ciblés (§3, après
> chaque nouveauté). Consigner tout écart avec le gabarit du §5.

---

## 1. Préparation (5 min)

### 1.1 Sauvegarde — TOUJOURS avant un reset

Ta base de dev contient des données réelles (notes Drive, anniversaires,
profils). Le seed démo les écrase. Avant tout `--reset` :

```bash
cp data/scranton.db data/scranton.db.bak-$(date +%Y%m%d)
cp -r data/chroma data/chroma.bak-$(date +%Y%m%d)
```

Restauration : recopier les fichiers dans l'autre sens, serveur éteint.

### 1.2 Choisir le mode

- **Mode démo** (recommandé pour le protocole complet) : données
  Dunder Mifflin prévisibles, les "attendus" du §2 sont calibrés dessus.
  `python -m backend.app.db.seed --reset`
- **Mode données réelles** : tes propres notes ; les attendus restent
  valables dans l'esprit, pas à la lettre.

### 1.3 Démarrer

```bash
source .venv/bin/activate
pytest                      # DOIT être vert avant de tester à la main
uvicorn backend.app.main:app --port 8001   # pas de --reload : redémarrer après tout changement backend
```

Ouvrir http://localhost:8001 — vérifier dans `.env` : `LLM_MODEL`
(mistral-medium-latest actuellement), `GDRIVE_FOLDER_ID` si test Drive.

---

## 2. Protocole complet (~45 min)

Cocher chaque case. Un "attendu" non conforme = bug à consigner (§5).

### 2.1 Tell Dwight — capture

1. Soumettre une note française riche (plusieurs sujets, une promesse,
   une observation sur une personne du roster, une entité inconnue) :
   - [ ] Segments proposés en **français** (jamais d'anglais, y compris sur reroll)
   - [ ] Découpage un sujet par segment, reformulation fidèle (rien d'inventé)
   - [ ] cold pour les faits, warm pour les observations subjectives
   - [ ] sensitivity 4-5 sur santé/conflit/départ/salaire uniquement
   - [ ] La promesse porte un tag `view:commitment`
   - [ ] Confidences VARIÉES : 0.9-1.0 seulement si l'entité est nommée ;
         une entité déduite ne dépasse jamais 0.8 ; jamais tout à 1.0
   - [ ] L'entité inconnue du roster n'a PAS de tag entité inventé
2. Soumettre une note vague ("j'ai réussi") :
   - [ ] UNE question de clarification, en français, qui vise l'info
         manquante (jamais "qui est je ?"), ton Dwight (zélé, pro)
   - [ ] Répondre dans le fil → segments produits, le fil peut boucler
3. Rejeter un segment avec commentaire :
   - [ ] Dwight repropose UN segment corrigé, même langue
   - [ ] "Forget it" sort de la boucle en rejet simple
4. Anniversaire dans une note ("l'anniv de X est le 12 mars") :
   - [ ] Suggestion de profil avec jour+mois, JAMAIS d'année affichée

### 2.2 La porte de validation (invariant fondateur)

1. Laisser un segment en "proposé", en rejeter un, en valider un :
   - [ ] Question Pam sur le contenu VALIDÉ → répond avec source
   - [ ] Question Pam sur le contenu PROPOSÉ ou REJETÉ → "rien en mémoire"
         (c'est le test le plus important du protocole)

### 2.3 Ask Pam — le RAG

1. Question française sur un fait validé :
   - [ ] Réponse française, fait exact, citation [n], sources datées dessous
2. La même en anglais :
   - [ ] Réponse anglaise (la langue suit la QUESTION)
3. Question dont la mémoire n'a qu'une partie ("que voulait me dire X ?") :
   - [ ] Rapporte ce qui EST là + dit ce qui manque (jamais un "rien" sec)
4. Question hors mémoire :
   - [ ] Le dit honnêtement, AUCUNE source citée, pas d'invention
5. Ton :
   - [ ] Chaleureux et direct, jamais au détriment de la précision

### 2.4 Pretzel Day + TWSS

1. Check-in autonome (écran Pretzel Day) :
   - [ ] 6 niveaux + note optionnelle, enregistrement OK, TWSS s'affiche
2. Fin du premier report du jour :
   - [ ] Panneau humeur inline APRÈS le dernier segment décidé
   - [ ] "Rather not say" : rien stocké, pas de TWSS
   - [ ] Humeur donnée : TWSS s'affiche
3. Reports suivants du jour :
   - [ ] TWSS direct, une seule fois par report (pas par segment)
4. Lisibilité TWSS :
   - [ ] Durée confortable (~4-6 s selon longueur), clic ferme tout de suite

### 2.5 Meet Toby

- [ ] Tendance d'équipe = moyenne d'HUMEURS datées, jamais un score de personne
- [ ] Les 4 signaux (declining_mood, low_mood, sensitive_warm ≥4,
      no_recent_checkin 7j) apparaissent sur les cas du seed (Ryan, Darryl)
- [ ] Formulations factuelles et datées, aucun jugement

### 2.6 Team, profils, Maire de Scranton

1. Carte membre :
   - [ ] Anniversaire = sélecteurs jour+mois, aucune année nulle part
   - [ ] Profil sauvegardé, rechargé après refresh
2. Maire (mettre l'anniversaire d'un membre à aujourd'hui, recharger) :
   - [ ] Bannière sidebar + badge "maire today" + célébration (1 fois par chargement)
   - [ ] Anniversaire à J-3 → rappel "upcoming" avec le profil en inspiration

### 2.7 Smart Summaries

Pour CHAQUE template (les 6) :
   - [ ] Sections remplies avec citations [n], sources exhaustives dessous
   - [ ] Langue du contenu = langue des extraits ; titres de sections inchangés
   - [ ] Section sans matière → une ligne honnête, pas de remplissage
   - [ ] annual_review : matière à discussion, JAMAIS un verdict sur la personne

### 2.8 Send Angela

- [ ] Export .md : contenu identique au résumé affiché
- [ ] Export .html : s'ouvre seul, imprimable (Cmd+P), rien de cassé

### 2.9 Transfer to Philly + trail de consentement

1. Ouvrir "Transfer to Philly" sur un membre :
   - [ ] Cold complet, warm trié par sensibilité croissante, cases décochées par défaut
2. Cycle complet : sélection → Start → (Save selection possible) →
   Preview fiche → Reviewed together → 2 noms → Sign both → download → Mark as transmitted :
   - [ ] Chaque étape n'offre QUE l'action légale suivante
   - [ ] Après review : la sélection ne peut plus changer
   - [ ] Après signature : hash affiché, fiche .md avec noms saisis (plus de lignes vides)
   - [ ] Télécharger N'EST PAS transmettre (statut inchangé après download)
   - [ ] Un 2e handover refuse de s'ouvrir tant que le 1er n'est pas sent
3. Ce qui ne doit JAMAIS y figurer :
   - [ ] Profil personnel, anniversaire, humeurs : absents du dossier ET de la fiche
   - [ ] Le warm retenu voyage en COMPTE, jamais en contenu

### 2.10 Ingestion Google Drive

- [ ] POST /api/v1/ingest/gdrive (ou relance depuis le protocole §3) :
      documents comptés, entrées créées, segments proposés en base
- [ ] Formats non supportés (PDF, images) : ignorés sans erreur
- [ ] Sans consentement/dossier : 503 avec message d'aide, jamais un crash

### 2.11 Config et coutures

- [ ] /api/v1/config/ui sert noms + avatars (rien de hardcodé côté UI)
- [ ] Changer `LLM_MODEL` dans .env + redémarrer → répond toujours
      (vérifiable dans les logs serveur)

---

## 3. Protocoles ciblés — nouveautés de juillet 2026

À dérouler après le protocole complet (ou seuls, après une retouche).

### 3.1 Passe de tuning (langue, calibration, ton, TWSS)

1. **Langue tenue sur reroll** : soumettre la MÊME note française 3 fois
   à Dwight (nouvelles entrées) :
   - [ ] 3/3 en français (le pin serveur doit tenir, pas 2/3)
2. Question Pam en anglais sur mémoire française :
   - [ ] Réponse 100 % anglaise (pin = langue de la question)
3. Summary sur extraits français :
   - [ ] Contenu français, titres de sections anglais intacts
4. Confidence (note avec 1 entité nommée + 1 déduite) :
   - [ ] Nommée ≥ 0.9, déduite ≤ 0.8, pas de tapis uniforme
5. TWSS : citation longue vs courte :
   - [ ] La longue reste visiblement plus longtemps

### 3.2 Trail de consentement handover

Version courte : dérouler §2.9.2 et vérifier en plus :
   - [ ] Re-télécharger la fiche signée 2 fois → fichiers strictement
         identiques (le hash SHA-256 doit correspondre à celui affiché ;
         `shasum -a 256 <fiche.md>` pour les curieux)

### 3.3 Levier modèle (A/B) et Ollama

1. `LLM_MODEL=mistral-small-latest` + redémarrage : capture OK, qualité moindre acceptée
2. `LLM_MODEL=mistral-medium-latest` (nominal) : retour à la normale
3. (Optionnel, exploration V2) `LLM_PROVIDER=ollama` + serveur ollama local :
   l'app répond ; la qualité 7B est documentée comme insuffisante — c'est
   un test de plomberie, pas de qualité

---

## 4. Non-régression automatisée (l'existant)

Ce qui tourne déjà, et que le mainteneur exécute avant chaque commit
(pratique en vigueur depuis M0 — chaque feature est arrivée avec ses
tests, la suite doit être verte avant tout push) :

| Commande | Contenu | Quand |
|---|---|---|
| `pytest` | 112 tests offline, déterministes (fakes scriptés, zéro réseau, zéro coût) | Avant chaque commit ; avant tout test manuel |
| `pytest -m integration` | 7 tests sur la vraie API Mistral (dont les golden queries anti-régression du seed) | Avant une démo ; après un changement de prompt ou de modèle |

Couvert : pipeline Dwight (parsing, validation, rework), porte de
validation → Chroma, Pam (grounding, sources, langue pinnée), mood/Toby,
profils/Maire (année effacée), summaries (registre, collecte SQL),
Angela, handover complet (dossier + trail de consentement + hash),
ingestion (sur mocks), coutures (factory, config), détecteur de langue.

Non couvert par l'automatique — c'est le rôle des §2-3 :
l'expérience UI réelle (au-delà des checks statiques), la qualité
subjective des sorties LLM (ton, pertinence), le flow OAuth réel.

Piste proposée (décision owner) : une CI GitHub Actions qui exécute
`pytest` à chaque push — la non-régression devient mécanique, plus
dépendante de la discipline du mainteneur.

---

## 5. Consigner un bug

Copier ce gabarit (dans une note, un ticket, ou directement à la session
suivante avec le mainteneur) :

```
Feature   : (ex. Ask Pam)
Étapes    : (ce que j'ai fait, dans l'ordre, avec les données utilisées)
Attendu   : (la case du protocole)
Obtenu    : (ce qui s'est passé, copier le texte exact si LLM)
Gravité   : bloquant / gênant / cosmétique
Reroll ?  : (pour les sorties LLM : est-ce reproductible 2 fois sur 3 ?)
```

Règle d'or pour les sorties LLM : un écart PONCTUEL de ton ou de
formulation n'est pas un bug (c'est de l'échantillonnage) ; un écart
RÉPÉTABLE (2/3) ou une violation d'invariant (langue, grounding,
année d'anniversaire, score de personne) en est toujours un.
