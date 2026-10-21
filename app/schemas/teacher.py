from app.schemas.profile import ProfileFields, ProfileRead, PublicProfileRead


class TeacherCreate(ProfileFields):
    pass


class TeacherUpdate(ProfileFields):
    pass


class TeacherRead(ProfileRead):
    pass


class TeacherPublicRead(PublicProfileRead):
    pass
