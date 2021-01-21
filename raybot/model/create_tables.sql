create table poi (
  id integer primary key,
  str_id text,
  name text not null,
  lon float not null,
  lat float not null,
  created timestamp not null default current_timestamp,
  updated timestamp not null default current_timestamp,
  needs_check boolean not null default 0,
  description text,
  keywords text, -- same as in poisearch table (see below)
  photo_out text,
  photo_in text,
  tag text, -- OSM key=value
  hours text, -- OSM format
  links text, -- json list of tuples: [['name': 'link'], ...]
  has_wifi boolean, -- this and next can be null
  accepts_cards boolean,
  phones text, -- semicolon-separated
  comment text,
  address text,
  in_index boolean not null default 1,
  house text, -- reference to a poi / str_id
  flor text,
  delete_reason text
);
create unique index poi_str_id_idx on poi (str_id);

create virtual table poisearch using fts3(name, keywords, tag, tokenize=unicode61);
-- When modifying poi, also modify rows in poisearch, using the "docid" column.
-- Typical search: select * from poi where rowid in (select rowid from poisearch where poisearch match 'tokens')

create table queue (
  id integer primary key,
  user_id integer not null,
  user_name text not null,
  ts timestamp not null default current_timestamp,
  poi_id integer not null,
  field text not null,
  old_value text,
  new_value text
);

create table poi_audit (
  id integer primary key,
  user_id integer not null,
  approved_by integer not null,
  ts timestamp not null default current_timestamp,
  poi_id integer not null,
  field text not null,
  old_value text,
  new_value text
);

create table roles (
    user_id integer not null,
    name text,
    role text not null,
    added_by text,
    added_on timestamp not null default current_timestamp
);
create index roles_user_idx on roles (user_id);

create table updates (
    id integer primary key,
    role text not null,
    message text not null,
    user_id integer not null,
    user_name text not null,
    ts timestamp not null default current_timestamp
);
create index updates_role_idx on updates (role);

create table file_ids (
    path text not null primary key,
    size integer not null,
    file_id text not null
);

create table stars(
    poi_id integer not null,
    user_id integer not null,
    ts timestamp not null default current_timestamp
);
create unique index stars_idx on stars (poi_id, user_id);
create index stars_user_idx on stars (user_id);
