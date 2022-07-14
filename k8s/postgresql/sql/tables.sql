-- DROP TYPE public."clip_status";

CREATE TYPE public."clip_status" AS ENUM (
	'new',
	'split',
	'validated',
	'splitting');

-- DROP TYPE public."gender_type";

CREATE TYPE public."gender_type" AS ENUM (
	'male',
	'female',
	'other',
	'unknown');

-- DROP TYPE public."source_status";

CREATE TYPE public."source_status" AS ENUM (
	'new',
	'downloading',
	'downloaded',
	'audio_extracting',
	'audio_extracted',
	'audio_converting',
	'audio_converted',
	'error',
	'checking_language',
	'bad_language',
	'ready_for_download',
	'vad_running',
	'vad_done',
	'splitting',
	'splitting_done');

-- DROP TYPE public."source_type";

CREATE TYPE public."source_type" AS ENUM (
	'youtube');

-- DROP TYPE public."variant_type";

CREATE TYPE public."variant_type" AS ENUM (
	'balear',
	'central',
	'nord-occidental',
	'septentrional',
	'valencià',
	'alguerès',
	'unknown');

-- public.sources definition

-- Drop table

-- DROP TABLE public.sources;

CREATE TABLE public.sources (
	source_id uuid NOT NULL DEFAULT gen_random_uuid(),
	url text NULL,
	"type" public."source_type" NULL,
	videopath text NULL,
	audiopath text NULL,
	audiopath_16 text NULL,
	metadata jsonb NULL,
	status public."source_status" NOT NULL DEFAULT 'new'::source_status,
	duration float4 NULL,
	sr int4 NULL,
	license varchar NULL,
	status_update timestamp NULL,
	has_captions bool NULL DEFAULT false,
	CONSTRAINT sources_pkey PRIMARY KEY (source_id)
);
CREATE INDEX idx_sources_url ON public.sources USING btree (url);


-- public.clips definition

-- Drop table

-- DROP TABLE public.clips;

CREATE TABLE public.clips (
	clip_id uuid NOT NULL DEFAULT gen_random_uuid(),
	source_id uuid NOT NULL,
	filepath text NULL,
	transcript_id uuid NULL,
	"start" float4 NULL,
	"end" float4 NULL,
	"language" varchar NULL,
	duration float4 NULL,
	status public."clip_status" NOT NULL DEFAULT 'new'::clip_status,
	status_update timestamp NULL,
	CONSTRAINT clips_pkey PRIMARY KEY (clip_id)
);


-- public.genders definition

-- Drop table

-- DROP TABLE public.genders;

CREATE TABLE public.genders (
	gender_id uuid NOT NULL DEFAULT gen_random_uuid(),
	gender public."gender_type" NOT NULL DEFAULT 'unknown'::gender_type,
	origin text NULL,
	clip_id uuid NULL,
	CONSTRAINT genders_pkey PRIMARY KEY (gender_id)
);


-- public.transcripts definition

-- Drop table

-- DROP TABLE public.transcripts;

CREATE TABLE public.transcripts (
	transcript_id uuid NOT NULL DEFAULT gen_random_uuid(),
	"text" text NOT NULL,
	transcriber text NOT NULL,
	clip_id uuid NOT NULL,
	CONSTRAINT transcripts_pkey PRIMARY KEY (transcript_id)
);


-- public.variants definition

-- Drop table

-- DROP TABLE public.variants;

CREATE TABLE public.variants (
	variant_id uuid NOT NULL DEFAULT gen_random_uuid(),
	variant public."variant_type" NOT NULL DEFAULT 'unknown'::variant_type,
	origin text NULL,
	clip_id uuid NULL,
	CONSTRAINT variants_pkey PRIMARY KEY (variant_id)
);


-- public.clips foreign keys

ALTER TABLE public.clips ADD CONSTRAINT clips_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);
ALTER TABLE public.clips ADD CONSTRAINT clips_transcript_id_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(transcript_id);


-- public.genders foreign keys

ALTER TABLE public.genders ADD CONSTRAINT genders_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(clip_id);


-- public.transcripts foreign keys

ALTER TABLE public.transcripts ADD CONSTRAINT transcripts_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(clip_id);


-- public.variants foreign keys

ALTER TABLE public.variants ADD CONSTRAINT variants_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES public.clips(clip_id);