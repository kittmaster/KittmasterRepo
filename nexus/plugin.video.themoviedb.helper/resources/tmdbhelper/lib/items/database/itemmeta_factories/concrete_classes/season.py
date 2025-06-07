from tmdbhelper.lib.items.database.itemmeta_factories.concrete_classes.basemedia import MediaItem, MediaItemArtworkRoutes
from tmdbhelper.lib.items.database.itemmeta_factories.concrete_classes.baseroutes import MediaItemInfoLabelItemRoutes, MediaItemInfoPropertyItemRoutes


class Season(MediaItem):
    infolabels_dbcitem_routes = (
        MediaItemInfoLabelItemRoutes.certification,
        MediaItemInfoLabelItemRoutes.trailer,
    )

    @property
    def art_dbclist_routes(self):
        return (
            MediaItemArtworkRoutes().configured_routes
            + MediaItemArtworkRoutes('tvshow').configured_routes
        )

    infoproperties_dbcitem_routes = (
        MediaItemInfoPropertyItemRoutes.watchedcount,
    )

    infoproperties_dbclist_routes = (
        *MediaItem.infoproperties_dbclist_routes,
        {
            'instance': ('network', None),
            'mappings': {'name': 'name', 'tmdb_id': 'tmdb_id', 'icon': 'logo', 'country': 'country'},
            'propname': ('network', ),
            'joinings': None
        }
    )

    @property
    def infolabels_dbclist_routes(self):
        return (
            *super().infolabels_dbclist_routes,
            (('network', None), 'name', 'studio'),
        )

    def get_infolabels_details(self):
        infolabels = super().get_infolabels_details()
        infolabels['episode'] = self.get_data_value('totalepisodes')
        return infolabels

    def get_infoproperties_custom(self, infoproperties):
        infoproperties = super().get_infoproperties_custom(infoproperties)
        for i in self.return_basemeta_db('custom', 'tvshow').cached_data:
            infoproperties[f"tvshow.{i['key']}"] = i['value']
        return infoproperties

    def get_unique_ids(self, unique_ids):
        unique_ids = super().get_unique_ids(unique_ids)
        for i in self.return_basemeta_db('unique_id', 'tvshow').cached_data:
            unique_ids[f"tvshow.{i['key']}"] = i['value']
        unique_ids['tmdb'] = unique_ids['tvshow.tmdb'] = self.parent_db_cache.tmdb_id
        return unique_ids

    def get_infoproperties_special(self, infoproperties):
        infoproperties = self.get_infoproperties_custom(infoproperties)
        try:
            infoproperties['totalepisodes'] = infoproperties['unwatchedepisodes'] = self.get_data_value('totalepisodes')
        except (TypeError, KeyError, IndexError):
            pass
        infoproperties = self.get_infoproperties_next_ep(infoproperties)
        return infoproperties
