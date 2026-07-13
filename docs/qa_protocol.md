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

Elle s'ouvre sur `http://localhost:8010/qa.html` et se suffit : ~40
points groupés par feature, chaque point = une action dans l'app + le
résultat attendu. Les notes de test sont fournies avec un bouton
**Copier** (rien à inventer, rien à taper). Les cases et remarques sont
conservées localement d'une session à l'autre ; **Copier le rapport**
génère un compte rendu prêt à coller pour la session de correction.

Elle couvre le produit RECADRÉ (2026-07-13) : le shell OS à deux rôles
(vues manager / vues équipier, identité, agents en boutons flottants),
la capture Dwight en overlay (langue, cold/warm, tags humains avec
confiance en toutes lettres, saisie qui suit la conversation,
clarification, suggestion de profil sans année), **la porte de
validation** (le test le plus important : Pam ignore tout segment non
validé), Ask Pam en Q&A ET en templates servis (question large sur une
entité → carte template ; ambiguë ou précise → Q&A ; langue de la
question), l'espace équipier (check-in pour soi, About me consenti,
étanchéité entre identités), le Dashboard + Maire, Michael's Desk
(agenda, brief 1:1, annual review = matière jamais verdict, exports),
Meet Toby en citations (les mots des gens, infos déclarées en lecture
seule, silence comme signal), **les checks négatifs** (vues Team et
Summaries disparues, saisie par procuration impossible, « file » et
tags cryptiques absents), et l'ingestion Drive (optionnelle).

Nota : le cycle Transfer to Philly ne fait plus partie de la passe
courante — son moteur reste testé par la suite automatisée, sa surface
revient en V2/V3 dans Michael's Desk (recadrage).

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
| `pytest` | 112 tests offline, déterministes (fakes scriptés, zéro réseau, zéro coût) | Avant chaque commit ; avant tout test manuel |
| `pytest -m integration` | 7 tests sur la vraie API Mistral (dont les golden queries anti-régression du seed) | Avant une démo ; après un changement de prompt ou de modèle |

Couvert : pipeline Dwight (parsing, validation, rework), porte de
validation → Chroma, Pam (grounding, sources, langue pinnée), mood/Toby,
profils/Maire (année effacée), summaries (registre, collecte SQL),
Angela, handover complet (dossier + trail de consentement + hash),
ingestion (sur mocks), coutures (factory, config), détecteur de langue.

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
