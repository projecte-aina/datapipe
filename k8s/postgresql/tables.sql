CREATE TABLE IF NOT EXISTS sources(
    source_id UUID PRIMARY KEY,
    url TEXT,
    type CHAR(40),
    videopath TEXT,
    audiopath TEXT,
    audiopath_16 TEXT,
    downloaded BOOL DEFAULT FALSE,
    converted BOOL DEFAULT FALSE,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS clips(
    clip_id UUID PRIMARY KEY,
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

        
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);