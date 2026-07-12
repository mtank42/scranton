# Scranton — Backlog
> Features identifiées avant le go, hors roadmap POC initiale.
> Chaque entrée inclut : description, scope suggéré, et questions à résoudre pour le data model.
> Last updated: 2026-07-12 — mise en cohérence avec le RECADRAGE (voir ci-dessous) lors de la passation Fable → Opus

---

## ⚠️ Recadrage 2026-07-12 — impact sur ce backlog

Le recadrage (`RECADRAGE_2026-07-12.md`, qui PRIME) change le cadre de
plusieurs entrées ci-dessous. Les notes **[RECADRAGE]** dans chaque
entrée font foi. En résumé :

- **Pam's Front Page** → l'écran Ask Pam n'existe plus ; l'idée vit
  désormais dans le **Dashboard manager** de la maquette.
- **Écran de revue des ingestions** → plus d'onglet Dwight ; à repenser
  dans la nouvelle architecture (badge sur l'action flottante ?).
- **Profil humain** → la saisie par le manager est ABOLIE ; le membre
  déclare lui-même via Pretzel Day ("About me - shared on purpose").
- **TWSS** → retour owner ajouté : "beaucoup plus drôles et visuels" (V2/V3).
- Les retours QA déjà en cours d'exécution (tags lisibles, confidence
  visible, box d'input sous les propositions) sont dans le RECADRAGE,
  pas ici : ce sont des corrections, pas des features.
- En attente de décision owner (hors backlog) : la **CI GitHub Actions**
  (`docs/qa_protocol.md` §3).

---

## Dwight propose de nouvelles entités (projets, clients, stakeholders)

**Catégorie** : Tell Dwight / Routage
**Priorité** : V1.x (demande explicite du owner, 2026-07-09 — "quand il ne sait pas où ranger, il propose la création")
**Origine** : test GDrive réel — les notes mentionnaient le projet "Matthaeus", absent de la base ; le monde clos a rabattu les segments sur "Tables mairie" à 0.7-0.8 (mésattribution plausible mais fausse).

### Description

Aujourd'hui le routage est en monde clos strict : une entité inconnue du roster est droppée (ou pire, rabattue sur une entité existante plausible). Attendu : quand Dwight rencontre un nom d'entité qu'il ne peut router, il **propose la création** (projet, client ou stakeholder) — exactement le modèle des profile_suggestions : transitoire, jamais persisté sans accord, le manager clique "Créer" ou "Ignorer". À la création, les tags du rapport en cours sont re-routés vers la nouvelle entité.

### Scope suggéré

Aucun changement de data model (les tables projects/clients/stakeholders existent). Une tâche 6 dans le prompt Dwight (entity_suggestions, même contrat que profile_suggestions), un endpoint POST de création + re-routage, les cartes suggestion dans l'UI du report. Le monde clos reste la règle pour les TAGS ; seule la SUGGESTION peut sortir du roster.

### Questions à résoudre

1. Anti-bruit : suggérer dès la première occurrence, ou seulement quand l'entité revient (2+ segments / 2+ notes) ?
2. Le rabattement observé (Matthaeus → Tables mairie à 0.7) : faut-il aussi durcir le prompt pour qu'une entité non nommée ne reçoive AUCUN tag entité plutôt qu'un tag plausible à confidence moyenne ?
3. Type ambigu (projet ou client ?) : Dwight propose le type avec sa confidence, le manager corrige au clic.

---

## Catalogue documentaire — "retrouver le plan de marquage livré"

**Catégorie** : Ask Pam / Ingestion / V2
**Priorité** : V2 (périmètre à acter — demande owner, 2026-07-09)
**Origine** : scénario onboarding ("un collaborateur débarque sur Matthaeus et demande le statut ET les docs de levée"). Ancré dans les stories : Helio semaine 5 (Lucas débarque, rien n'est documenté nulle part) et "la couche de sens au-dessus du chaos" (storytelling §Helio). Le data model l'anticipait : `source_type` = deliverable / quote / purchase_order, `origin_ref` conserve le pointeur source.

### Description

Deux étages, PAS de doc-RAG plein texte :
1. **Sources cliquables** (V1.x, trivial) : les sources de Pam exposent l'`origin_ref` des segments ingérés — chaque fait pointe vers son document Drive.
2. **Catalogue par entité** (V2) : à l'ingestion, TOUS les fichiers du dossier (PDF, decks, compta inclus) sont catalogués en métadonnées seules (nom, type, date, lien) et routés vers projets/clients comme des segments. Pam répond alors "statut + les 4 documents liés (liens)". Scranton indexe l'EXISTENCE des documents, jamais leur contenu : la couche de sens, pas la GED. Cohérent souveraineté (les docs restent dans leur source).

### Questions à résoudre

1. Indexer le CONTENU des documents (vrai doc-RAG, "que dit le deck sur la dilution ?") : volontairement HORS de cette entrée — changement de nature du produit (contourne la porte de validation, indexe de la compta sensible, concurrence NotebookLM). À ne rouvrir que si le terrain le réclame.
2. Le catalogue passe-t-il par la validation manager (cohérence invariant) ou entre-t-il directement (ce sont des métadonnées, pas du contenu humain) ?
3. Schéma : nouvelle table `documents` → session data model dédiée obligatoire.
4. Lien avec Transfer to Philly cas 2 : l'onboarding entrant et la passation sortante consomment le même catalogue.

---

## Écran de revue des ingestions

**Catégorie** : Tell Dwight / Ingestion / UI
**Priorité** : V1.x (petit, découvert avec le owner le 2026-07-09)
**Origine** : premier run GDrive réel — l'ingestion crée entrées et segments proposés, mais l'UI n'a aucun écran pour les relire : la validation n'est accessible que par API.

### Description

Une vue "à valider" listant les segments proposés en attente, groupés par entrée, avec les mêmes cartes validate/reject/rework que le flux de capture. Sans elle, l'ingestion Drive est une impasse UX : les documents entrent, rien ne les présente au manager.

> **[RECADRAGE 2026-07-12]** Plus d'onglet Dwight : penser plutôt un
> badge/compteur sur l'action flottante "+ Tell Dwight" qui ouvre la
> file des propositions en attente (capture ET ingestion, même flux).

### Questions à résoudre

1. Où : onglet dédié, ou état de repos de l'écran Dwight (symétrique de Pam's Front Page) ?
2. Le bouton "Pull Drive" lui-même n'existe pas dans l'UI (POST manuel aujourd'hui) : même écran ?

---

## TWSS adaptatif à l'humeur

**Catégorie** : That's What She Said / Reward
**Priorité** : V1 (candidate, petit)
**Origine** : feedback démo MLP (juillet 2026)

### Description

La récompense s'adapte à l'humeur déclarée du jour : pas de blague vaseuse à quelqu'un qui va mal (plutôt un gif de chat mignon), un but de foot légendaire pour quelqu'un en super forme. Les citations Michael Scott restent le mode par défaut quand l'humeur est neutre ou inconnue.

> **[RECADRAGE 2026-07-12]** Retour owner ajouté au périmètre : les TWSS
> doivent devenir "beaucoup plus drôles et visuels" (V2/V3) — pas
> seulement adaptatifs. Le texte seul ne suffit pas.

### Questions à résoudre

1. Sourcing des assets (gifs/vidéos) : bibliothèque locale (poids du repo ?) vs API externe (Giphy = tracker, contraire à l'esprit) vs sélection statique embarquée.
2. Mapping humeur → registre de récompense : par niveau (6 registres ?) ou par zones (bien / neutre / mal).

---

## Pam's Front Page — les dernières nouvelles importantes

**Catégorie** : Ask Pam / UI / Proactivité
**Priorité** : V1 (candidate)
**Origine** : feedback démo MLP (juillet 2026) — "tant qu'il n'y a pas de question, le panel sources est inutile, voire incongru"

> **[RECADRAGE 2026-07-12]** L'écran Ask Pam n'existe plus (Pam est une
> action flottante). L'idée reste valable mais son lieu naturel est
> désormais le **Dashboard de la vue manager** (maquette) : les "news"
> y complètent le moodboard et l'avancement projets. À re-cadrer là.

### Description

Aujourd'hui, l'écran Ask Pam est vide tant qu'aucune question n'est posée. L'idée : cet état de repos devient un **tableau des dernières nouvelles importantes** — Pam met en avant ce qui mérite l'attention du manager sans qu'il ait à demander. Premier pas vers la Pam proactive (qui culmine en V1 avec les rappels Maire de Scranton).

### Questions à résoudre avant de coder

1. **Comment mesurer l'importance ?** Candidats disponibles sans changement de schéma : récence, `sensitivity_level` élevé, `data_type` warm, tags `view_type = commitment` (engagements = importants par nature), signaux Meet Toby actifs. Ou un score d'importance proposé par Dwight à la segmentation (nouveau champ → session data model dédiée).
2. **Importance ≠ surveillance** : le tableau met en avant des faits datés, jamais un classement de personnes. Les règles Toby s'appliquent.
3. **Chevauchement avec Meet Toby** : Toby = santé d'équipe, Front Page = actualité de la mémoire (engagements qui arrivent à échéance, décisions récentes, clients en attente). Trancher la frontière pour éviter deux dashboards concurrents.

---

## Profil humain + Maire de Scranton

**Catégorie** : Team member profile / Culture / Lien social
**Priorité** : V1 (profil humain) — V1 (maire de Scranton, événement anniversaire)
**Origine** : session data model — observation sur les clans Helio (fondateurs vs nouveaux)

### Problème

Scranton capte la couche professionnelle. Mais le lien entre équipiers se crée par la connaissance mutuelle des personnes, pas des rôles. Dans une équipe qui scale vite (comme Helio), les "nouveaux" restent des inconnus. Scranton peut contribuer à briser ça.

### Profil humain — "ce qu'ils aiment"

> **[RECADRAGE 2026-07-12 — le paragraphe ci-dessous est OBSOLÈTE sur un
> point capital]** : la saisie par le manager est ABOLIE (verdict QA du
> owner : "c'est l'opposé absolu de l'esprit du service"). Le membre
> déclare lui-même ce qu'il partage, via son espace Pretzel Day
> ("About me - shared on purpose", voir la maquette), avec la mention
> explicite que c'est visible du manager seul. Les suggestions Dwight
> ne valent que sur les propos du membre LUI-MÊME. Le manager consulte
> (dans Toby), il ne saisit jamais.

Chaque team member a un profil personnel en plus de son profil professionnel. ~~Données déclarées par le manager (observées en 1:1, en conversation)~~ Saisies par le membre lui-même.

Exemples : né le 11 février, fan de New Order, obsédé par la période Madchester, Moebius, les oursons en guimauve.

Ce n'est pas un formulaire RH. C'est ce que tu saurais d'un collègue après 3 mois si tu l'écoutais vraiment.

**Mécanisme** : Tell Dwight peut extraire ces informations depuis une note de 1:1. Si le manager écrit "Maxime m'a dit qu'il est né le 11 février et qu'il est fan de New Order", Dwight propose de l'ajouter au profil humain de Maxime.

### Maire de Scranton — l'anniversaire comme rituel

Le jour de l'anniversaire d'un membre de l'équipe, il devient **Maire de Scranton** pour 24h :
- L'interface Scranton adopte ses couleurs préférées (si renseignées) ou une palette générée depuis ses centres d'intérêt
- Un badge "Maire de Scranton" apparaît sur son profil toute la journée
- Pam envoie un rappel au manager **une semaine avant** : "L'anniversaire de Maxime est dans 7 jours. Tu veux préparer quelque chose avec l'équipe ?" — avec un rappel de ses centres d'intérêt pour inspirer
- That's What She Said se déclenche automatiquement le jour J

C'est un rituel annuel, prédictible, positif. Zéro bureaucratie. Pam gère.

### Impact sur le data model

**`birthday`** : champ date à ajouter sur `team_members`. Intégré au schéma initial (décision W1).

**`personal_profile`** : texte libre sur `team_members`, ou table séparée `team_member_profile` si on veut structurer par catégories (musique, culture, food, etc.). À décider en session.

**Propriété des données — décision W1** : le profil humain appartient au team member, pas au manager. Chacun ne dévoile que ce qu'il veut bien. Le manager ne peut ni modifier ni supprimer ces données. En POC (pas d'auth) : le manager saisit pour compte du membre. En V2 : le membre édite directement son propre profil.

C'est le split de propriété fondamental de Scranton : données professionnelles = manager. Données personnelles = membre de l'équipe.

### Questions à résoudre

1. **`personal_profile` : texte libre ou table structurée ?** Texte libre est plus naturel pour la saisie ("fan de New Order, obsédé par Madchester") mais moins queryable. Table structurée avec catégories permet à Pam de faire des corrélations ("deux membres de l'équipe aiment le jazz, tu le savais ?").

2. **Extraction automatique par Dwight** : quand Dwight repère une information personnelle dans une note, propose-t-il systématiquement de l'ajouter au profil humain, ou seulement si le manager le demande ?

3. **Visibilité entre équipiers** : en V2, les membres voient-ils le profil humain des autres ? C'est la dimension "lien social" — mais c'est aussi une question de consentement.

### Notes complémentaires

- Le "Maire de Scranton" est nommé dans l'univers The Office (Scranton, PA). À confirmer comme nom final.
- Ce mécanisme répond directement au cas Helio : les "nouveaux" ne resteraient pas des inconnus si Scranton rendait les personnes visibles en tant que personnes, pas seulement en tant que rôles.
- Potentiel fort pour le storytelling produit et le marketing — c'est la feature qui montre que Scranton n'est pas un outil RH.

---

## Tell Dwight — Capture vocale asynchrone ("dans le camion")

**Catégorie** : Tell Dwight / Capture
**Priorité** : V2
**Origine** : session use cases menuiserie — le moment de vie non capturé par définition

### Description

Mode de capture vocale pour Tell Dwight, pensé pour les moments hors bureau : chantier, trajet, machine à café. Le manager dicte une note courte comme un vocal WhatsApp. Dwight ne l'interrompt pas. Quand le manager repasse au bureau, Dwight présente le batch de la journée : "Tu m'as laissé 3 notes aujourd'hui. Je te propose de les ranger là, ici et encore là." Le manager valide ou ajuste le routage proposé.

### UX flow

1. Mobile : le manager enregistre une note vocale (interface simple, un bouton)
2. La note est transcrite et mise en file d'attente (statut `pending`)
3. Dwight traite en arrière-plan : transcription → segmentation → proposition de routage
4. Au retour au bureau : notification "X notes en attente de validation"
5. Le manager valide ou ajuste le routage segment par segment
6. Les segments validés entrent dans le pipeline normal (ChromaDB + vues)

### Impact sur le data model

Aucun changement de schéma. Le champ `source_type` sur `entries` accueille simplement `voice_note`. Le pipeline Dwight est identique.

### Questions à résoudre avant de coder

**1. Moteur de transcription**
Whisper est d'OpenAI — hors stack. Options souveraines :
- Whisper open source en local (modèle `whisper.cpp` sur Mac Mini M4 — viable)
- Web Speech API native du navigateur (pas de serveur, mais qualité variable et dépendance au navigateur)
- Mistral speech-to-text si disponible au moment du dev V2

**2. Interface mobile**
PWA (Progressive Web App) dans le même frontend HTML/CSS/JS, ou application native ? La PWA est cohérente avec le stack POC et évite un second projet.

**3. Offline-first**
Si le manager est sans réseau sur le chantier, la note doit pouvoir être enregistrée localement et synchronisée au retour. À définir avec l'architecture de déploiement V2.

### Notes complémentaires

- Ce mode résout le cas d'usage le plus fréquent et le moins capturé : la décision prise hors bureau
- Le modèle batch ("je te propose X rangements") est intentionnel — Dwight n'interrompt pas, il attend
- À distinguer de Whisper Jim (chat éphémère) : ici c'est de la capture pour Pam, pas de la conversation

---

## Transfer to Philly

**Catégorie** : Transitions / Handover
**Priorité** : ~~V1 (cas 1)~~ **V2/V3 (owner, recadrage 2026-07-12)** — cas 2 + interopérabilité ensuite
**Naming** : final, dans l'univers Dunder Mifflin (Scranton → Philadelphia, même État)

> **[RECADRAGE 2026-07-12]** Le moteur du cas 1 est CONSTRUIT et testé
> (dossier, divulgation sélective, fiche signable, table
> `handover_validations` — voir `docs/transfer_to_philly.md`) : il ne se
> jette pas, il attend. Sa surface quitte la carte Team (supprimée) et
> rejoindra **Michael's Desk** — ce que cette entrée disait déjà
> ("le manager demande à Michael une fiche", cas 2 "depuis Michael's
> Desk"). Le owner a resséquencé : la passation au nouveau manager est
> son seul but, elle arrive en V2/V3 avec Send Angela. Les questions
> data model 1 (cold/warm natif) et la traçabilité de validation sont
> résolues depuis.

### Description

Feature de gestion des transitions — quand un employé change d'équipe ou quand le manager est remplacé. Facilite la passation de connaissance sans perdre la mémoire collective ni exposer des données sensibles sans consentement.

### Cas 1 — Transfert d'un employé vers une autre équipe

1. Le manager demande à Michael une fiche complète sur l'employé concerné
2. Michael génère deux blocs distincts :
   - **Données froides** : faits objectifs (projets, compétences, tâches, présence, historique)
   - **Données chaudes** : observations subjectives du manager (notes 1:1, évaluations, signaux faibles), triées par ordre de sensibilité
3. Le manager sélectionne ce qu'il souhaite transmettre parmi les données chaudes (toutes les données froides sont a priori transmissibles)
4. Le document proposé est soumis à l'employé, qui peut proposer des modifications
5. Les deux parties valident le document final
6. Angela exporte et envoie au Scranton du nouveau manager

**Scope POC** : génération de la fiche + export PDF validé par les deux parties.

### Cas 2 — Succession du manager

1. Le manager sortant déclenche "Transfer to Philly" depuis Michael's Desk
2. Michael génère une fiche par membre de l'équipe (mode batch pour N membres)
3. Le manager fait le même travail qu'en cas 1 pour chaque fiche
4. Le manager peut supprimer ses données chaudes personnelles (observations, notes subjectives qui lui appartiennent en propre) avant transmission
5. Toby génère un rapport de synthèse d'équipe pour le successeur
6. Deux options de transmission :
   - Angela envoie l'ensemble des fiches au successeur
   - Transmission d'une instance Scranton "nettoyée" (données chaudes personnelles supprimées) incluant l'accès à Pam

**Scope V1** : batch de fiches + export structuré.
**Scope V2** : transmission d'instance + interopérabilité entre Scranton.

---

### Alignement RGPD

La boucle de validation employé (étape 4 du cas 1) n'est pas optionnelle — elle est alignée avec le droit d'accès aux données personnelles (RGPD/CNIL). C'est une contrainte légale transformée en feature produit.

---

### Questions pour le data model — à résoudre avant de coder

**1. Distinction froid / chaud native dans le schéma**
La séparation données froides / données chaudes doit être un attribut de chaque entrée dès la conception, pas un tag ajouté en retro-fit.
→ *Chaque note, observation ou événement doit porter un champ `data_type` (cold / warm) et un champ `sensitivity_level` (1–5 ?) dès le schéma initial.*

**2. Propriété des données chaudes**
Certaines données chaudes "appartiennent" au manager (ses observations personnelles). D'autres appartiennent à l'équipe (tendances mood, actions de 1:1).
→ *Faut-il un champ `owner` (manager_id vs team) sur chaque entrée sensible ? Comment modéliser le droit de suppression sélective ?*

**3. Export de Pam (ChromaDB)**
"Transmettre l'accès à Pam" en cas 2 = exporter la base vectorielle.
→ *Définir un format d'export ChromaDB dès l'architecture initiale. Quelles collections sont transmissibles ? Avec quel niveau de filtrage ?*

**4. Consentement employé — traçabilité**
La validation à deux parties doit être auditée (qui a validé quoi, quand).
→ *Table `handover_validations` avec statuts (proposed / employee_reviewed / both_validated / sent) et timestamps. Signatures ou simple boolean ?*

**5. Interopérabilité entre instances (V2)**
"Envoyer au Scranton du nouveau manager" suppose un protocole d'échange entre instances.
→ *Pour le POC : export ZIP ou PDF suffit. Pour V2 : définir un format d'import/export structuré (JSON ?) avant de coder l'export POC, pour ne pas avoir à tout refaire.*

**6. Suppression sélective des données chaudes du manager sortant**
Le manager doit pouvoir purger ses observations personnelles sans toucher aux données d'équipe.
→ *La suppression doit être traçable (soft delete avec `deleted_by_manager_at`) plutôt qu'une suppression physique, pour des raisons d'audit.*

---

### Notes complémentaires

- Pour une équipe de 10, le cas 2 doit être en **batch** — une interface séquentielle fiche par fiche serait inutilisable.
- Le naming interne des états du workflow (proposed / reviewed / validated / sent) doit être défini une fois et réutilisé partout.
- Feature à mentionner dans le README comme différenciateur : "knowledge continuity across team transitions."

---

## Pistes écosystème — à explorer avant V2

### LaSuite numérique (DINUM)
Open source, souverain, utilisable par le privé. APIs disponibles sur `integration.lasuite.numerique.gouv.fr`.
- **Grist Core** (self-hostable) : tableur/base de données collaboratif. Pertinent pour Send Angela (exports structurés).
- **Docs** : éditeur collaboratif. Pourrait alimenter l'affichage des Smart Summaries.
- Argument de positionnement pour le README : "même philosophie que les outils numériques de l'État français."

### Albert API
LLM souverain français (DINUM). Alternative ou complément à Mistral si le projet évolue vers le secteur public ou un positionnement EU renforcé.

### GitHub MCP
À installer avant le go. Permet de gérer issues, PRs, et repo depuis Claude Code sans changer de contexte. Le repo doit être propre dès le premier commit.

---

## Recommandations extensions VS Code

- `Python` + `Pylance` — indispensable
- `REST Client` — tester les routes FastAPI sans quitter l'éditeur
- `SQLite Viewer` — inspecter la base SQLite visuellement
- `GitLens` — historique git ligne par ligne
- `Thunder Client` — API testing léger
