# Protocole QA — Scranton

> Doc opérateur, en français : c'est le mode d'emploi du propriétaire.
> Trois niveaux : le test manuel via le **launcher QA** (§1-2, avant une
> démo ou après un jalon), la non-régression automatisée (§3, exécutée
> par le mainteneur à chaque commit), le gabarit de bug (§4).

---

## 1. Lancer un test : double-clic, rien d'autre

Dans le Finder, à la racine du projet : double-cliquer
**`Scranton QA.command`**. C'est tout. Le launcher :

1. crée un **environnement jetable** sous `data/qa/` — base et mémoire
   vectorielle isolées : **les données réelles ne sont jamais touchées**,
   aucune sauvegarde à faire, rien à restaurer après ;
2. y sème le jeu de démo **Dunder Mifflin** (Ryan, Kelly, Darryl... et
   leurs storylines calibrées : les "attendus" de la checklist reposent
   dessus), identique à chaque lancement ;
3. démarre un serveur de test dédié (port 8010, jamais celui du vrai
   Scranton) et ouvre la **checklist interactive** dans le navigateur.

Pour **arrêter** : fermer la fenêtre Terminal qui s'est ouverte (ou
Ctrl+C dedans). Relancer plus tard repart d'un environnement neuf.

Seule dépendance à la vraie config : la clé Mistral du `.env` (Dwight et
Pam appellent le vrai modèle) et, pour le test Drive optionnel, le
dossier `GDRIVE_FOLDER_ID` configuré.

## 2. La checklist interactive

Elle s'ouvre sur `http://localhost:8010/qa.html` et se suffit : chaque
point = une action dans l'app + le résultat attendu. Les notes de test
sont fournies avec un bouton **Copier** (rien à inventer, rien à
taper). Les cases et remarques sont conservées localement d'une session
à l'autre ; **Copier le rapport** génère un compte rendu prêt à coller
pour la session de correction.

**Le périmètre est glissant (règle owner, 2026-07-16)** : ce qu'une
passe QA a validé et que la suite automatisée couvre en non-régression
**sort de la checklist** — on ne reteste pas à la main ce que la
machine surveille. Chaque version de la checklist = une passe éclair
sur le vivant (ce qui dépend du vrai modèle) + les nouveautés jamais
testées par le owner.

**Version courante (v5, 2026-07-16)**, quatre sections :

1. **Passe éclair** (4 points) : shell, une capture Dwight avec
   décisions, la porte de validation, une réponse Pam citée — le cœur
   validé en QA 1-2, revérifié en 5 minutes parce qu'il parle au vrai
   modèle.
2. **Le volet Pam, deux mémoires** : Darryl l'archiviste (bandeau,
   bac + classement un clic, badge document, famille de versions,
   tableur catalogué) et l'historique des notes (« Show more », repli)
   — livrés APRÈS la QA 2, jamais testés.
3. **Édition des documents** (le gros de la passe) : Save and edit,
   accordéon, édition manuelle, révision Dwight en diff calculé, le
   delta des nouveautés (badge, tissage, dismiss), la carte Pam vers
   l'éditeur, l'entrée au corpus des docs clients et l'exception
   personnes.
4. **Drive réel** (optionnelle, EN DERNIER : le sync remplace le corpus
   de démo) : formats réels, familles de versions, comportement du bac.

Sorti de la passe courante (validé + sous non-régression automatisée) :
le shell détaillé, les vues équipier/Dashboard/Toby, les templates
servis et redirects personnes de Pam, les checks négatifs du recadrage,
la clarification Dwight et l'acquittement vie privée, les exports
Angela. Le cycle Transfer to Philly reste hors passe (moteur testé par
la suite, surface V2/V3). L'ancienne ingestion Drive par Dwight a
disparu de la checklist : le corpus documentaire passe par Darryl.

Règle d'or pour juger une sortie du modèle : un écart **ponctuel** de
formulation n'est pas un bug (échantillonnage) ; un écart **répétable**
(2 fois sur 3) ou une **violation d'invariant** (langue, faits inventés,
année d'anniversaire, score de personne) en est toujours un.

## 3. Non-régression automatisée (côté mainteneur)

Ce qui tourne déjà, exécuté avant chaque commit (pratique en vigueur
depuis M0 — chaque feature est arrivée avec ses tests, la suite doit
être verte avant tout push) :

| Commande | Contenu | Quand |
|---|---|---|
| `pytest` | 166 tests offline, déterministes (fakes scriptés, zéro réseau, zéro coût) | Avant chaque commit ; avant tout test manuel |
| `pytest -m integration` | 7 tests sur la vraie API Mistral (dont les golden queries anti-régression du seed) | Avant une démo ; après un changement de prompt ou de modèle |

Couvert : pipeline Dwight (parsing, validation, rework), porte de
validation → Chroma, Pam (grounding, sources, langue pinnée, deux
mémoires, redirects personnes), Darryl (sync, routage, versions, bac,
classement), moteur d'édition (persistance, delta, diff, réviseur pur,
exception personnes, protection du sync), mood/Toby, profils/Maire
(année effacée), summaries (registre, collecte SQL), Angela, handover
complet (dossier + trail de consentement + hash), ingestion (sur
mocks), coutures (factory, config), détecteur de langue.

Non couvert par l'automatique — c'est le rôle de la checklist :
l'expérience UI réelle, la qualité subjective des sorties LLM (ton,
pertinence), le flow OAuth réel.

Piste proposée (décision owner) : une CI GitHub Actions qui exécute
`pytest` à chaque push — la non-régression devient mécanique, plus
dépendante de la discipline du mainteneur.

## 4. Consigner un bug

La zone "remarques" de chaque section de la checklist suffit (elle part
dans le rapport). Pour un bug isolé hors session QA, ce gabarit :

```
Feature   : (ex. Ask Pam)
Étapes    : (ce que j'ai fait, dans l'ordre, avec les données utilisées)
Attendu   : (la case de la checklist)
Obtenu    : (ce qui s'est passé, copier le texte exact si LLM)
Gravité   : bloquant / gênant / cosmétique
Reroll ?  : (pour les sorties LLM : est-ce reproductible 2 fois sur 3 ?)
```
