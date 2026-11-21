import random
import os
from xmlparser import XML_Parser
import logging

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
# ethnic value 1: the first of these found in the players nationalities is used
LIGHT_SKINNED_PRIORITY = ("South American", "YugoGreek", "SpanMed", "SAMed", "Italmed", "EECA")
LIGHT_SKINNED_FALLBACK = frozenset(["Scandinavian", "Seasian", "Central European", "Caucasian",
                                    "African", "Asian", "MENA", "MESA"])

class Mapper:
    def __init__(self, img_dir, prf_manager):
        self.img_dir = img_dir
        self.profile_manager = prf_manager
        self.eth_map = {}
        eth_dirs = [f.name for f in os.scandir(img_dir) if f.is_dir()]
        for dir in eth_dirs:
            # only images can be used as faces, not files like Thumbs.db or .DS_Store
            dir_imgs = set([os.path.splitext(f.name)[0] for f in os.scandir(img_dir+dir)
                            if f.name.lower().endswith(IMAGE_EXTENSIONS) and f.is_file()])
            self.eth_map[dir] = dir_imgs

        logger = logging.getLogger('NewGAN App')
        self.logger = logger

    def generate_mapping(self, rtf_data, mode, duplicates=False):
        mapping = []
        xml_data = {}
        log = self.logger.info
        get_ethnic = self.profile_manager.get_ethnic

        for eth, pool in self.eth_map.items():
            if not isinstance(pool, set):
                self.eth_map[eth] = set(pool)
        if mode in ["Preserve", "Overwrite"]:
            xml_parser = XML_Parser()
            xml_data = xml_parser.parse_xml(self.img_dir+"config.xml")

            if not duplicates:
                # faces that are already in use are not available anymore
                for values in xml_data.values():
                    pool = self.eth_map.get(values["ethnicity"])
                    if pool is not None:
                        pool.discard(values["image"])

        self._pick_lists = {}
        seen = set()
        total = len(rtf_data)
        for i, player in enumerate(rtf_data):
            uid = player[0]
            p_ethnic = None
            n2_ethnic = None
            if player[2]:
                n2_ethnic = get_ethnic(player[2])
            n1_ethnic = get_ethnic(player[1])
            if n1_ethnic is None:
                log("Mapping for {} is missing. Skipping player {}".format(player[1], uid))
                continue
            log("{}/{}: {}, {}, {}".format(i, total, player, n1_ethnic, n2_ethnic))
            eth_val = player[3]
            if not eth_val.isdecimal() or int(eth_val) > 10:
                log("Ethnic value {} is invalid. Most likely a bug in the view. Skipping player {}".format(eth_val, uid))
                continue
            eth_val = str(int(eth_val))
            # a player that is listed more than once only gets one face
            if uid in seen:
                log("Player {} is listed more than once. Skipping duplicate".format(uid))
                continue
            seen.add(uid)
            # if player is in config.xml and we use preserver or overwrite handle it properly
            if uid in xml_data:
                if mode == "Preserve":
                    log("Preserve: {} {} {}".format(uid, xml_data[uid]["ethnicity"], xml_data[uid]["image"]))
                    continue
                elif mode == "Overwrite":
                    del xml_data[uid]
            if eth_val == "1":
                p_ethnic = self._light_skinned_ethnic(n1_ethnic, n2_ethnic)
            elif eth_val in ("3", "6", "7", "8", "9"):
                # SAMed with 7 is light-skinned
                if "SAMed" == n1_ethnic and eth_val == "7":
                    p_ethnic = "SAMed"
                # South American with 7 is light-skinned
                elif "South American" == n1_ethnic and eth_val == "7":
                    p_ethnic = "South American"
                else:
                    p_ethnic = "African"
            elif eth_val == "10":
                if "South American" == n1_ethnic:
                    p_ethnic = "South American"
                else:
                    p_ethnic = "Asian"
            elif eth_val == "2":
                p_ethnic = "MENA"
                if "MESA" == n1_ethnic or "MESA" == n2_ethnic:
                    p_ethnic = "MESA"
            elif eth_val == "5":
                p_ethnic = "Seasian"
            elif eth_val == "0":
                p_ethnic = "Central European"
                if "Scandinavian" == n1_ethnic or "Scandinavian" == n2_ethnic:
                    p_ethnic = "Scandinavian"
                elif "Caucasian" == n1_ethnic or "Caucasian" == n2_ethnic:
                    p_ethnic = "Caucasian"
            elif eth_val == "4":
                p_ethnic = "MESA"

            if p_ethnic not in self.eth_map:
                log("No image folder for ethnicity {}. Skipping player {}".format(p_ethnic, uid))
                continue
            # pick image based on p_ethnic
            player_img = self.pick_image(p_ethnic, duplicates)
            if player_img is None:
                log("Ethnicity {} has no faces left for mapping. Skipping player {}".format(p_ethnic, uid))
                continue
            mapping.append([uid, p_ethnic, player_img])
        self._pick_lists = {}
        if mode in ["Overwrite", "Preserve"]:
            self.post_rtf_hook(mapping, xml_data)
        return mapping

    def _light_skinned_ethnic(self, n1_ethnic, n2_ethnic):
        # the nationality with the highest priority decides
        for eth in LIGHT_SKINNED_PRIORITY:
            if eth == n1_ethnic or eth == n2_ethnic:
                return eth
        if n1_ethnic in LIGHT_SKINNED_FALLBACK or n2_ethnic in LIGHT_SKINNED_FALLBACK:
            return "South American"
        return None

    def get_xml_images(self, xml_data):
        return [i["image"] for i in xml_data.values()]

    def pick_image(self, ethnicity, duplicates=False):
        selection_pool = self.eth_map[ethnicity]
        if len(selection_pool) == 0:
            return None
        # Turning the pool into a sequence is expensive for big facepacks, so
        # it is only done once per ethnicity instead of once per player.
        pick_lists = getattr(self, "_pick_lists", None)
        if pick_lists is None:
            pick_lists = self._pick_lists = {}
        pick_list = pick_lists.get(ethnicity)
        if pick_list is None or len(pick_list) != len(selection_pool):
            pick_list = pick_lists[ethnicity] = list(selection_pool)

        if duplicates:
            return random.choice(pick_list)

        # uniform pick without replacement: swap the pick to the end and pop it
        idx = random.randrange(len(pick_list))
        choice = pick_list[idx]
        pick_list[idx] = pick_list[-1]
        pick_list.pop()
        selection_pool.remove(choice)
        return choice

    def post_rtf_hook(self, mapping, xml_data):
        for uid, values in xml_data.items():
            mapping.append([uid, values["ethnicity"], values["image"]])
