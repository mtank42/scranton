# Scranton — Backlog
> Features identifiées avant le go, hors roadmap POC initiale.
> Chaque entrée inclut : description, scope suggéré, et questions à résoudre pour le data model.
> Last updated: 2026-07-15 — **Darryl l'archiviste LIVRÉ** (session du
> jour, voir le statut de l'entrée) ; l'ordre des chantiers vit désormais
> dans PRODUCT_ROADMAP.md §4 (indispensable / nécessaire / utile / agréable)

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

## Édition des documents via Dwight — la touche finale du manager

**Catégorie** : Michael's Desk / Ask Pam / Dwight
**Priorité** : **PROCHAINE GROSSE SESSION** (arbitrage owner, QA 2026-07-14 : « le manager n'a aucun moyen de modifier ce qu'il reçoit, c'est inutilisable »)
**Origine** : première passe QA du produit recadré — les documents générés (agenda, brief 1:1, annual review, templates Pam) sont en lecture seule.

### Description

Le manager ajuste un document généré en dialoguant avec Dwight (« ajoute le point sur le devis, enlève la section 2, reformule l'intro ») et garde la touche finale. Concerne Michael's Desk ET le bouton « Adjust with Dwight » des cartes Pam. Inclut l'accordéon (replier une section traitée).

### Décisions owner (2026-07-14, réponses au triage QA 2)

1. **Persistance : OUI** — un document édité devient un objet persisté (« oui, bien sûr ! »). Les summaries non touchés restent vivants ; la première édition fige. ⚠️ Implique probablement une table → mini-session data model dans la session.
2. **« Edit with Dwight » est TOUJOURS accompagné d'un « Edit manually »** — le owner réalise que bien souvent la modif à la main est plus pratique. Les deux gestes, partout : Desk ET cartes Pam.
3. **Le contexte voyage avec l'instruction** (QA 2 : « en l'état, il ne sert à rien s'il faut tout lui répéter ») — Dwight reçoit le document en cours d'ajustement, jamais une instruction nue.

### Use case d'ouverture de session (à jouer avant le schéma)

Le owner génère le brief 1:1 de Ryan sur le Desk. Il dit à Dwight
« enlève le point sur les commissions, ajoute que le reporting Q3 est
à jour » ; puis il corrige une tournure À LA MAIN ; il sauvegarde. Une
semaine passe, trois nouveaux segments validés concernent Ryan. Il
rouvre : que voit-il ? (LA tension de la session : le template vivant
se recalcule, le document édité est un instantané figé — comment
l'écart se montre-t-il, et comment se résorbe-t-il ?) Enfin il partage
ou exporte le résultat.

### Questions pour la session (data model comprise)

1. **Data model (le créneau dédié, règle 2)** : la table des documents
   édités — quoi persister (sections ? markdown ? sources ?), l'objet
   d'origine (template + cible + date de génération), les horodatages
   d'édition. Versions d'un même document édité : historique ou
   dernier état seul ?
2. **La tension vivant/figé** : la 1re édition fige (décision acquise).
   Le document figé doit-il AFFICHER que la mémoire a bougé depuis
   (« N segments validés depuis l'édition ») et offrir un
   « régénérer » (qui perd ou re-applique les édits ?) — à trancher en
   jouant le use case.
3. **Un document édité entre-t-il au corpus de Darryl ?** (une ligne
   `documents` avec source `scranton`, interrogeable par Pam et badgée
   *document*). Convergence tentante — une seule notion de document
   dans le produit — mais à arbitrer explicitement : elle ferait
   entrer du contenu généré-par-LLM-puis-édité dans la mémoire de Pam.
4. Frontière Dwight/Pam côté implémentation : un seul appel LLM
   (doc + instruction → doc révisé) via `complete_validated` ?
5. L'accordéon (replier une section traitée) : dans cette session ou
   avec les exports ?
6. Lien avec « Exports & partage » — l'édition doit déboucher sur un
   format actionnable ; et **Oscar consommera ce moteur** sur les
   fiches clients/projets (édition en contexte depuis le tableau de
   bord) : concevoir l'API du moteur indépendante de la surface Desk.

### Micro-sujets à traiter en ouverture de session (owner, 2026-07-15)

1. **Volet Pam, l'historique** : les 5 dernières notes Dwight AU-DESSUS
   des 5 derniers documents Darryl, avec un bouton « Afficher plus »
   qui déplie 10 de plus, puis 10 de plus, etc. (constat de session
   Darryl : cet historique de notes n'existait pas encore — le fil
   Dwight est par session ; décision owner : on le construit).
2. **Premier sync Darryl sur le Drive réel du owner** (OK owner, avec
   sa réserve : « je ne suis pas une PME avec clients et projets » —
   donc PAS un test du routage, qui enverra l'essentiel au bac ; c'est
   un test des FORMATS réels, des familles de versions, de la tenue de
   la sync à l'échelle, et du comportement du bac quand il est plein).

---

## Refonte des célébrations — TWSS et Maire

**Catégorie** : That's What She Said / Maire / Reward
**Priorité** : session dédiée (feedback QA owner, 2026-07-14 — verbatim : « pour l'instant c'est plus une nuisance qu'une récompense » ; le popin Maire est « sinistre et intrusif »)

> **[2026-07-15]** En attendant cette session, **TWSS et Maire sont
> DÉSACTIVÉS** (owner, QA 2 : « c'est trop mauvais, que du bruit et de
> la friction ») : flag `CELEBRATIONS = false` dans `frontend/app.js`,
> le code et le backend restent intacts. La QA 2 ajoute un cas concret :
> recevoir une blague après un check-in « je ne vais pas bien » est
> malvenu — l'adaptation à l'humeur est un levier central de la refonte.

### Description

Repenser fréquence, déclencheurs et forme : gamification (rareté, variété, montée en valeur), TWSS pas à chaque micro-action, célébration Maire discrète et festive plutôt qu'un overlay bloquant. Absorbe l'entrée « TWSS adaptatif à l'humeur » ci-dessous (l'adaptation à l'humeur devient un des leviers). Note owner : le manager aussi a le droit d'être Maire de Scranton (voir l'entrée « Identité manager ») 🙂

---

## Oscar — le tableau de bord des opérations & la naissance des entités

**Catégorie** : Nouvelle vue manager / Tell Dwight / Routage / Data model
**Priorité** : session dédiée avec data model (cadrage owner 2026-07-15, pendant la session Darryl) — après « Édition des documents » (l'édition livre le moteur « à la main ou avec Dwight, le contexte voyage » que la vue consomme)
**Origine** : réflexion owner 2026-07-15 : « dans une entreprise, c'est au manager de gérer les nouveaux clients et projets ». Constat PM : le roster n'a AUCUN chemin de création aujourd'hui (le seed est le seul) — la douleur Matthaeus de la QA 2. Absorbe l'entrée « Dwight propose de nouvelles entités » ci-dessous.

### Décisions owner (2026-07-15) — ne pas re-débattre

1. **Le manager gère les entités.** Dwight continue de repérer les
   nouveaux noms chez les collaborateurs, mais ça lance un workflow :
   il rassemble ces infos en un draft et le route vers le manager.
2. **Pas de limbes : un statut, pas un brouillon.** Un nouveau client
   potentiel = une entité de plein droit sur le TEMPLATE CLIENT avec un
   statut **prospect** ; idem pour les projets non signés / non validés
   par le client : statut **piste**. Conséquence élégante (règle les
   questions 1 et 2 de Fabrice d'un coup) : UNE ligne par nom (dédup
   naturelle), les mentions s'accumulent en tags dessus dès le premier
   jour, Pam est interrogeable dessus, et la « validation » est une
   transition de statut (prospect → client) — rien à rétro-taguer.
3. **La vue : Oscar, tableau de bord des opérations** (nouvelle vue
   manager, le comptable qui tient les livres). **Trois onglets :
   Clients / Projets / Prospects & pistes.** On y voit tout, on
   interroge Pam depuis une fiche, on édite à la main ou avec Dwight
   dans le contexte, on traite les drafts (éditer, valider, etc.).
4. **Les équipiers voient sur leur board** la liste des projets sur
   lesquels ils travaillent et les clients concernés (dérivable des
   tags validés, même mécanique SQL que la réponse deux-équipiers de
   Pam — pas de data model).
5. **Templates à affiner plus tard** : jauges pour les projets vendus
   en temps-homme (« on verra plus tard »). Garde-fou étoile polaire à
   écrire le moment venu : jauges de consommation du PROJET, jamais un
   taux par personne.

### Questions pour la session (data model comprise)

1. **Data model** : statut sur `clients` (prospect / actif) et
   `projects` (piste / signé) — champ sur les tables validées, donc
   session dédiée (règle 2). Les stakeholders suivent-ils ? Une
   transition de statut est-elle datée/tracée (qui a validé, quand) ?
2. **Le geste de création** : Dwight crée-t-il la ligne prospect en
   SILENCE (façon Darryl : signal déterministe = nom explicitement
   présenté comme nouveau ?) ou propose-t-il une carte transitoire que
   le manager clique pour créer (façon profile_suggestions) ? Anti-
   bruit hérité : créer dès la 1re occurrence ou à la récurrence ?
   Le 3e onglet est le bac calme dans les deux cas — jamais de popin.
3. **Monde clos élargi** : les prospects/pistes entrent-ils au roster
   injecté à Dwight dès leur naissance (taguables, avec leur statut
   visible dans le badge) ? C'est le sens de la décision 2 — à
   confirmer côté prompt et UI des tags.
4. **[QA 2, hérité]** Granularité du rejet en cours de dialogue
   Dwight (« reprends à l'échange précédent ») — même session.
5. **La vue** : 4e vue manager dans la nav (Oscar avec son avatar) —
   cohérence avec le deck (les slides = boussole UX) à vérifier avant
   maquette. « Interroger Pam depuis une fiche » = volet Pam pré-
   contextualisé ?
6. **Darryl s'y branche** : la fiche client/projet du tableau de bord
   est la surface naturelle des documents routés (`document_tags`) —
   les afficher dès la V1 de la vue ?

---

## ~~Dwight propose de nouvelles entités (projets, clients, stakeholders)~~

> **[2026-07-15] ABSORBÉE par « Oscar — le tableau de bord des
> opérations » ci-dessus** (le modèle carte transitoire est remplacé
> par les statuts prospect/piste ; les questions anti-bruit et la
> granularité du rejet y sont reprises). Conservée pour l'historique.

**Catégorie** : Tell Dwight / Routage
**Priorité** : ~~V1.x~~ absorbée (demande explicite du owner, 2026-07-09 — "quand il ne sait pas où ranger, il propose la création")
**Origine** : test GDrive réel — les notes mentionnaient le projet "Matthaeus", absent de la base ; le monde clos a rabattu les segments sur "Tables mairie" à 0.7-0.8 (mésattribution plausible mais fausse).

### Description

Aujourd'hui le routage est en monde clos strict : une entité inconnue du roster est droppée (ou pire, rabattue sur une entité existante plausible). Attendu : quand Dwight rencontre un nom d'entité qu'il ne peut router, il **propose la création** (projet, client ou stakeholder) — exactement le modèle des profile_suggestions : transitoire, jamais persisté sans accord, le manager clique "Créer" ou "Ignorer". À la création, les tags du rapport en cours sont re-routés vers la nouvelle entité.

### Scope suggéré

Aucun changement de data model (les tables projects/clients/stakeholders existent). Une tâche 6 dans le prompt Dwight (entity_suggestions, même contrat que profile_suggestions), un endpoint POST de création + re-routage, les cartes suggestion dans l'UI du report. Le monde clos reste la règle pour les TAGS ; seule la SUGGESTION peut sortir du roster.

### Questions à résoudre

1. Anti-bruit : suggérer dès la première occurrence, ou seulement quand l'entité revient (2+ segments / 2+ notes) ?
2. Le rabattement observé (Matthaeus → Tables mairie à 0.7) : faut-il aussi durcir le prompt pour qu'une entité non nommée ne reçoive AUCUN tag entité plutôt qu'un tag plausible à confidence moyenne ?
3. Type ambigu (projet ou client ?) : Dwight propose le type avec sa confidence, le manager corrige au clic.
4. **[QA 2, 2026-07-14] Granularité du rejet en cours de dialogue** : quand la clarification part dans la bonne direction puis dérive, le rejet emporte le point ENTIER, pas le dernier échange — perte de temps vécue en signalant que Matthaeus était un nouveau projet. Prévoir un « reprends à l'échange précédent » (ou équivalent) dans cette même session.

---

## Darryl l'archiviste — le corpus documentaire au service de Pam

**Catégorie** : Ask Pam / Ingestion / Architecture / Nouvel agent
**Priorité** : **L'INDISPENSABLE #1** (roadmap 2026-07-15) — session dédiée avec data model
**Statut** : **LIVRÉ (session du 2026-07-15)** — pipeline complet (sync, routage déterministe + LLM en appoint, bac non classé, familles de versions), une Pam sur deux mémoires (sources badgées, liens cliquables), bande d'archive dans le volet Pam (5 derniers docs + bac + classement en un clic + bouton Sync), seed enrichi (4 docs de démo, l'équipier Darryl renommé Val). Doc de référence : `docs/darryl.md`. Arbitrages de session complémentaires (owner) : versions = « le plus récent par défaut, TOUTES sur demande explicite à Pam » (route déterministe) ; PAS d'écran d'audit dédié — Darryl travaille dans l'ombre, son travail est surfacé par le volet Pam ; souplesse de routage = roster comme signal (pas de convention de dossiers à configurer) + seuil réglable + bac comme filet. Restent OUVERTS pour plus tard : sources futures (Notion/Teams/Slack/GMail, principes déjà actés ci-dessous), watch/sync automatique (V1 = bouton).
**Origine** : test GDrive de la QA 2, puis session PM du 2026-07-15 (casquettes PM/architecte/Fabrice). Verdict owner : « C'est le RAG. J'ai une boîte qui tourne, je branche Scranton sur le RAG, je ne veux pas avoir à tout apprendre à Dwight. De la matière pour Pam, pas pour Dwight. »

### Le cadrage juste (correction owner, 2026-07-15)

Ce n'est PAS un changement d'invariant : c'est la porte de validation
qui prend sa forme documentaire, **dans les specs depuis le 1er jour**
(`source_type` = deliverable/quote/purchase_order, `origin_ref`).
**Un document rangé dans le dossier partagé avec Scranton est, par ce
geste même, validé par l'humain.** Le faire repasser par Dwight serait
demander deux fois la même signature. Dwight structure l'humain non
structuré, point barre. Deux mémoires donc :
- **couche humaine** : notes → Dwight → validation explicite (inchangé) ;
- **corpus documentaire** : dossier partagé → Darryl → Pam, directement.

### Darryl, le nouvel agent

L'archiviste « invisible » : mandat étroit (détecter, extraire, découper,
router, versionner), aucune décision humaine à voler. Thématiquement
parfait (le foreman du warehouse). Invisible au quotidien, **auditable à
la demande** : une surface minimale montre ce qu'il a lu, quand, où il
l'a rangé — et permet de corriger un routage. ⚠️ Le seed démo a un
équipier Darryl : le renommer (la map `characters` est la couture).

### Décisions arbitrées (owner, 2026-07-15) — ne pas re-débattre

1. **La porte = le dossier** : partager un dossier avec Scranton, c'est
   valider son contenu. La compta reste hors périmètre parce qu'on ne
   partage pas ce dossier-là (la peur n°1 de Fabrice).
2. **Darryl route SEUL, jamais de pari** : routage silencieux quand
   c'est sûr (signaux déterministes d'abord : arborescence, nom de
   fichier ; LLM en appoint), **bac « non classé »** sous le seuil —
   jamais de rabattement plausible (leçon Matthaeus). Un doc non classé
   reste interrogeable, il ne nourrit pas les fiches.
3. **Une seule Pam, deux mémoires** : réponse tissée, sources badgées
   *mémoire d'équipe* / *document*. Architecte : deux collections
   vectorielles (cycles de vie différents), une interface de requête.
4. **Liens cliquables vers les docs : V1, non négociable** (la demande
   n°1 de Fabrice — `origin_ref` + `webViewLink`, quasi gratuit).
5. **Formats** : doc, ppt, pdf indexés en contenu ; **xls catalogué
   seulement** (nom, date, client, lien — pas de contenu aplati en
   bouillie). Extraction derrière un seam par type MIME ; Notion et
   Teams = adaptateurs ultérieurs (owner : « nous verrons ça plus tard »).
6. **Le corpus documentaire est cold par construction** : la règle Pam
   cold-only s'étend naturellement.

### Use case d'ouverture de session (à jouer avant le schéma)

Fabrice, agence de marketing online, 5 personnes, quinze ans de Drive.
Il partage `Clients/` (pas `Compta/`). Il demande : « qu'est-ce qu'on a
livré à Techni-Pneus au premier trimestre ? » → réponse qui tisse la
mémoire d'équipe (« promis le 15, souci de facturation signalé ») et les
documents (« le rapport SEO de mars », lien cliquable). Ses trois peurs
à traiter dans le design : la compta (réglée par la porte-dossier), les
six versions de `Rapport_SEO_final_V3_DEF(1).pdf`, les formats réels.

### Questions pour la session (data model comprise)

1. Table(s) `documents` + chunks : l'équivalent documentaire de
   « SQLite est la vérité du texte » (on ne relit pas le Drive à chaque
   réponse) — forme exacte, `origin_ref`, `webViewLink`.
2. Cycle de vie : resync (nouveau doc, doc modifié, doc supprimé),
   fréquence, déclencheur (bouton ? watch ?).
3. Versions : « le plus récent gagne » suffit-il ? Détection des
   familles de fichiers (V1/V2/DEF) : heuristique ou tant pis ?
4. Seuil de routage et forme exacte du bac « non classé ».
5. Où vit la surface d'audit de Darryl (vue dédiée ? section du
   Dashboard ?) — absorbe l'entrée « Écran de revue des ingestions ».

### Sources futures (owner, 2026-07-15 — hors session V1 de Darryl)

Notion, Teams, Slack et **GMail** (« bourré d'infos primordiales ») =
des adaptateurs sur le seam d'ingestion de Darryl, plus tard. Pour le
mail, principe VALIDÉ par le owner (2026-07-15) : une boîte mail est
privée par nature, la porte « ranger = valider » ne s'y transpose pas —
donc **une fraction des mails, d'intérêt commun, validée par CHAQUE
utilisateur** (manager ou équipier), est versée aux archives de Darryl.
Geste candidat : un label « Scranton » posé sur le mail. Même
philosophie que le dossier partagé, autre geste — et c'est le premier
flux où les ÉQUIPIERS alimentent directement la mémoire documentaire.

---

## Liens vers les outils de l'entreprise — sur le board de chacun

**Catégorie** : My board / Dashboard / UI
**Priorité** : L'UTILE (owner, 2026-07-15)

### Description

Les outils de l'entreprise (Notion, Slack, Teams, GMail...) en accès
direct **sur le board de chaque membre de l'équipe, manager ou non**.
Scranton assume son rôle d'OS : le point d'entrée de la journée, qui
ouvre sur le reste. Simple : des liens configurables, pas d'intégration
profonde (ça, c'est les connecteurs Darryl).

### Questions à résoudre

1. Qui configure la liste : l'admin pour toute l'équipe (cohérent avec
   la session identité/onboarding), avec des ajouts perso par membre ?
2. Côté manager : sur le Dashboard, ou sur un futur board manager
   (dépend de la session identité) ?

---

## Catalogue documentaire — "retrouver le plan de marquage livré"

**Catégorie** : Ask Pam / Ingestion / V2
**Priorité** : V2 (périmètre à acter — demande owner, 2026-07-09)

> **[2026-07-15] ABSORBÉE par « Darryl l'archiviste » ci-dessus.** La
> question 1 ci-dessous (« indexer le CONTENU = hors périmètre ») est
> renversée par l'arbitrage owner ; l'étage catalogue/liens (métadonnées
> + `origin_ref`) devient le traitement des xls et le socle des liens
> cliquables dans la session Darryl. Conservée pour l'historique du
> raisonnement.
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

## Exports & partage — des documents qui servent à quelque chose

**Catégorie** : Send Angela / Michael's Desk / My board
**Priorité** : session produit dédiée (owner, QA 1 et QA 2 : « il faudra vraiment changer les formats d'export, je ne sais pas quoi en faire »)

### Description

Deux volets décidés le 2026-07-14 :

1. **Formats utiles** : .md/.html bruts ne servent à rien au quotidien.
   Cadrer les vrais débouchés (impression propre ? PDF ? Grist/Docs via
   les pistes LaSuite ? copie formatée ?) — à instruire avec les cas
   d'usage réels du owner.
2. **Le partage dans l'app plutôt que l'export** (owner, QA 2) :
   - L'**ODJ de la réunion d'équipe** est visible sur le **My board de
     chaque équipier** ; chacun peut **suggérer d'y ajouter des items**
     à discuter.
   - Le **brief 1:1 est partagé** entre le manager et l'équipier
     concerné, même logique.

### Questions à résoudre

1. Le partage suppose que le document généré soit persisté → dépend de la décision de persistance de la session Édition (acquise : oui).
2. Une suggestion d'item équipier est-elle une entrée Dwight (validée par le manager) ou un objet propre ?
3. Frontière avec le warm : un ODJ partagé à l'équipe ne doit JAMAIS embarquer du matériau Toby/warm — le partage force une hygiène cold-only des documents partagés.

---

## Identité du manager, rôle admin & onboarding d'équipe

**Catégorie** : Architecture / Rôles / Onboarding
**Priorité** : session dédiée (owner, QA 2 2026-07-14 — « comment on commence avec Scranton la 1re fois ? »)
**Origine** : confusion QA 2 sur Darryl — le manager n'a AUCUNE identité dans le système (le sélecteur d'identité équipier prend juste le premier du roster). Et aucun workflow ne crée équipe/comptes : le seed est le seul chemin.

### Décisions owner déjà prises (2026-07-14)

- **Le manager est l'admin**, avec une **identité à part** (pas un team_member déguisé).
- En tant qu'admin, **il crée les comptes** de chaque nouveau collaborateur.
- **Pas de suivi de sa propre humeur** : le manager n'a pas besoin de son Pretzel Day mood (« je pense que c'est inutile »).
- **Mais il a le droit d'être Maire de Scranton** 🙂 — son anniversaire existe donc quelque part.
- Plus tard : **co-admin** (passer un membre co-admin en cas d'absence du manager).

### Questions à résoudre

1. Data model : une identité manager à part = probablement une table ou un rôle → session data model dédiée (règle 2).
2. Premier lancement : le workflow d'initialisation (créer le manager, créer l'équipe, importer un roster ?) — le « day one » de Scranton.
3. Lien avec la création d'entités par Dwight (nouveau collaborateur mentionné dans une note → proposer la création du compte ?).
4. Anniversaire du manager sans mood tracking : où le déclare-t-il ?

---

## Écran de revue des ingestions

**Catégorie** : Tell Dwight / Ingestion / UI
**Priorité** : ~~V1.x~~ **ABSORBÉE par « Darryl l'archiviste » (2026-07-15)** — l'ingestion documentaire ne passe plus par la validation Dwight ; ce besoin devient la **surface d'audit de Darryl** (question 5 de cette entrée). Conservée pour l'historique.
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
