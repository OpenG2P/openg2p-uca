CREATE TABLE [user]
(
    [user_id] INTEGER NOT NULL,
    [name] NVARCHAR(120),
    [dob] DATE,
    CONSTRAINT [pk_user] PRIMARY KEY  ([user_id])
);

