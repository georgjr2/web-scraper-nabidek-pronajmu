import json
import logging
import re
from urllib.parse import urljoin

import requests

from disposition import Disposition
from scrapers.rental_offer import RentalOffer
from scrapers.scraper_base import ScraperBase


class ScraperSreality(ScraperBase):

    name = "Sreality"
    logo_url = "https://www.sreality.cz/img/icons/android-chrome-192x192.png"
    color = 0xCC0000
    base_url = "https://www.sreality.cz"

    disposition_mapping = {
        Disposition.FLAT_1KK: "2",
        Disposition.FLAT_1: "3",
        Disposition.FLAT_2KK: "4",
        Disposition.FLAT_2: "5",
        Disposition.FLAT_3KK: "6",
        Disposition.FLAT_3: "7",
        Disposition.FLAT_4KK: "8",
        Disposition.FLAT_4: "9",
        Disposition.FLAT_5_UP: ("10", "11", "12"),
        Disposition.FLAT_OTHERS: "16",
    }

    _category_type_to_url = {
        0: "vse",
        1: "prodej",
        2: "pronajem",
        3: "drazby"
    }

    _category_main_to_url = {
        0: "vse",
        1: "byt",
        2: "dum",
        3: "pozemek",
        4: "komercni",
        5: "ostatni"
    }

    _category_sub_to_url = {
            2: "1+kk",
            3: "1+1",
            4: "2+kk",
            5: "2+1",
            6: "3+kk",
            7: "3+1",
            8: "4+kk",
            9: "4+1",
            10: "5+kk",
            11: "5+1",
            12: "6-a-vice",
            16: "atypicky",
            47: "pokoj",
            37: "rodinny",
            39: "vila",
            43: "chalupa",
            33: "chata",
            35: "pamatka",
            40: "na-klic",
            44: "zemedelska-usedlost",
            19: "bydleni",
            18: "komercni",
            20: "pole",
            22: "louka",
            21: "les",
            46: "rybnik",
            48: "sady-vinice",
            23: "zahrada",
            24: "ostatni-pozemky",
            25: "kancelare",
            26: "sklad",
            27: "vyrobni-prostor",
            28: "obchodni-prostor",
            29: "ubytovani",
            30: "restaurace",
            31: "zemedelsky",
            38: "cinzovni-dum",
            49: "virtualni-kancelar",
            32: "ostatni-komercni-prostory",
            34: "garaz",
            52: "garazove-stani",
            50: "vinny-sklep",
            51: "pudni-prostor",
            53: "mobilni-domek",
            36: "jine-nemovitosti"
        }


    def _create_link_to_offer(self, offer) -> str:
        cat_type = self._category_type_to_url[offer["categoryTypeCb"]["value"]]
        cat_main = self._category_main_to_url[offer["categoryMainCb"]["value"]]
        cat_sub = self._category_sub_to_url.get(offer["categorySubCb"]["value"], "byt")

        locality = offer["locality"]
        parts = [locality.get("citySeoName"), locality.get("cityPartSeoName"), locality.get("streetSeoName")]
        locality_str = "-".join(p for p in parts if p)

        return urljoin(self.base_url, f"/detail/{cat_type}/{cat_main}/{cat_sub}/{locality_str}/{offer['id']}")

    def build_response(self) -> requests.Response:
        url = self.base_url + "/hledani/pronajem/byty/brno"

        logging.debug("Sreality request: %s", url)

        return requests.get(url, headers=self.headers)

    def get_latest_offers(self) -> list[RentalOffer]:
        response = self.build_response()

        if response.status_code != 200:
            logging.warning("Sreality: unexpected status %s", response.status_code)
            return []

        match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', response.text)
        if not match:
            logging.warning("Sreality: __NEXT_DATA__ not found in response")
            return []

        data = json.loads(match.group(1))
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]

        results = None
        for q in queries:
            qkey = q.get("queryKey", [])
            if isinstance(qkey, list) and len(qkey) > 0 and qkey[0] == "estatesSearch":
                results = q["state"]["data"]["results"]
                break

        if results is None:
            logging.warning("Sreality: estatesSearch query not found in page data")
            return []

        desired_subs = set(self.get_dispositions_data())

        items: list[RentalOffer] = []

        for item in results:
            if str(item["categorySubCb"]["value"]) not in desired_subs:
                continue

            image_url = ""
            if item.get("images"):
                image_url = "https:" + item["images"][0]["url"] + "?fl=res,800,600,3|shr,,20|jpg,80"

            locality = item["locality"]
            location_parts = [locality.get("city", ""), locality.get("cityPart", "")]
            location = " - ".join(p for p in location_parts if p)

            items.append(RentalOffer(
                scraper=self,
                link=self._create_link_to_offer(item),
                title=item["name"],
                location=location,
                price=item["priceCzk"],
                image_url=image_url
            ))

        return items
