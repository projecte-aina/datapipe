CREATE TYPE source_type AS ENUM ('youtube', 'tv3', 'ib3', 'tiktok');
CREATE TYPE source_status AS ENUM ('new', 'downloading', 'downloaded', 'audio_extracting', 'audio_extracted', 'audio_converting', 'audio_converted', 'error');
CREATE TYPE clip_status AS ENUM ('new', 'splitting', 'split', 'validated');
CREATE TYPE gender_type AS ENUM ('male', 'female', 'other', 'unknown');
CREATE TYPE variant_type AS ENUM ('balear', 'central', 'nord-occidental', 'septentrional', 'valencià', 'alguerès', 'unknown');

CREATE TABLE IF NOT EXISTS sources(
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT,
    type source_type,
    videopath TEXT,
    audiopath TEXT,
    audiopath_16 TEXT,
    downloaded BOOL DEFAULT FALSE,
    converted BOOL DEFAULT FALSE,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS clips(
    clip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(source_id),
    filepath TEXT,
    "start" float4 NULL,
	"end" float4 NULL,
);

CREATE TABLE IF NOT EXISTS transcripts(
    transcript_id UUID PRIMARY KEY,
    text TEXT,
    transcriber CHAR(40),
    clip_id UUID REFERENCES clips(clip_id)
);

alter table clips add transcript_id UUID REFERENCES transcripts(transcript_id);

        
CREATE INDEX IF NOT EXISTS idx_sources_url ON public.sources USING btree (url);

create user grafana with encrypted password 'datapipe';
grant connect on database datapipe to grafana;
grant usage on database datapipe to grafana;
grant usage on schema public to grafana;
grant select on all tables in schema public to grafana;
grant select on all sequences in schema public to grafana;
alter default privileges in schema public grant select on tables to grafana;

CREATE TABLE IF NOT EXISTS genders (
	gender_id uuid NOT NULL DEFAULT gen_random_uuid(),
	gender gender_type NOT NULL DEFAULT 'unknown'::gender_type,
	origin text NULL,
	clip_id uuid NULL,
	CONSTRAINT genders_pkey PRIMARY KEY (gender_id),
	CONSTRAINT genders_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);

CREATE TABLE IF NOT EXISTS variants (
	variant_id uuid NOT NULL DEFAULT gen_random_uuid(),
	variant variant_type NOT NULL DEFAULT 'unknown'::variant_type,
	origin text NULL,
	clip_id uuid NULL,
	CONSTRAINT variants_pkey PRIMARY KEY (variant_id),
	CONSTRAINT variants_clip_id_fkey FOREIGN KEY (clip_id) REFERENCES clips(clip_id)
);
