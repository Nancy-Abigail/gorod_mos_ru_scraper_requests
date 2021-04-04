from sqlalchemy import create_engine, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, sessionmaker, Session, scoped_session
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///database/result.sqlite', echo=False, connect_args={'check_same_thread': False})
Base = declarative_base()


# It's easier to control session at an orchestrator side to control its lifecycle and avoid using same session
# in different threads. All commits, rollbacks and session closures should be managed at an orchestrator side as well.
def new_session():
    return scoped_session(sessionmaker(bind=engine))


class Report(Base):
    # Table
    __tablename__ = 't_reports'

    # Columns
    id = Column(Integer, primary_key=True)
    object_id = Column(Integer, ForeignKey('t_objects.id'))
    author_id = Column(Integer, ForeignKey('t_authors.id'))
    theme = Column(String)
    date = Column(String)
    text = Column(String)
    image_links = Column(String)

    # Relations
    object = relationship('Object', back_populates='reports')
    author = relationship('Author', back_populates='reports')

    def push(self, session: Session):
        origin = None
        # noinspection PyBroadException
        try:
            origin = session.query(self.__class__).filter(self.__class__.id == self.id).one_or_none()
        except Exception:
            pass

        if origin is None:
            session.add(self)


class Author(Base):
    # Table
    __tablename__ = 't_authors'

    # Columns
    id = Column(Integer, primary_key=True)
    full_name = Column(String)

    # Relations
    reports = relationship('Report', back_populates='author')

    def push(self, session: Session):
        origin = None
        # noinspection PyBroadException
        try:
            origin = session.query(self.__class__).filter(self.__class__.id == self.id).one_or_none()
        except Exception:
            pass

        if origin is None:
            session.add(self)


class Object(Base):
    # Table
    __tablename__ = 't_objects'

    # Columns
    id = Column(Integer, primary_key=True)
    type = Column(String)
    address = Column(String)
    lat = Column(String)
    lon = Column(String)

    # Relations
    reports = relationship('Report', back_populates='object')

    def push(self, session: Session):
        origin = None
        # noinspection PyBroadException
        try:
            origin = session.query(self.__class__).filter(self.__class__.id == self.id).first()
        except Exception:
            pass

        if origin is None:
            session.add(self)

    @staticmethod
    def already_exist(id):
        session = new_session()

        objects = session.query(Object).filter(Object.id == id).all()
        if len(objects) > 0:
            return True
        else:
            return False


def main():
    # Create/update database schema
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    main()
