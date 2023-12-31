"""Utility functions go here"""
from datetime import datetime
import json
import numpy as np
from astropy.coordinates import SkyCoord, match_coordinates_sky, Angle

# Import configurations
config = json.load(open("config.json", encoding="utf-8"))
META_DATA_KEY = config["META_DATA_KEY"]
TEMP_FOLDER = config["TEMP_FOLDER"]

# Catch errors
def catalog_type_check(catalog):
    """Checks if the catalog is a path to a JSON file or a dictionary.
    
    Args:
        catalog: The catalog to be checked.

    Returns:
        The catalog as a dictionary.
    """
    try:
        catalog = json.load(open(catalog, encoding="utf-8"))
    except TypeError as e:
        if not isinstance(catalog, dict):
            raise TypeError("Catalog must be a path to a JSON file or a dictionary.") from e

    return catalog

def catalog_name_check(catalog, catalog_name):
    """Checks if a specified catalog had already been compiled.
    
    Args:
        catalog: The catalog to be checked.
        catalog_name: The name of the catalog to be checked.

    Returns:
        The name of the catalog if it is in the collection.
    """
    collection = list(catalog[META_DATA_KEY]['Included titles'].keys())

    if catalog_name not in collection:
        raise ValueError("Catalog was never added to the collection.")
    elif catalog_name is None:
        raise ValueError("Catalog name must be specified.")

    return catalog_name

def dict_depth(d):
    """Finds the depth of a nested dictionary.
    
    Args:
        d: The dictionary to be checked.

    Returns:
        The depth of the dictionary.
    """
    if not isinstance(d, dict) or not d:
        # If not a dictionary or an empty dictionary, depth is 0
        return 0

    # Recursive call to find the depth of nested dictionaries
    depths = [dict_depth(value) for value in d.values()]

    # Return the maximum depth plus 1 for the current dictionary
    return max(depths) + 1

def save_to_json(data, savepath):
    """Saves data to a JSON file."""
    with open(savepath, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent = 4)

def member_count(cat):
    """Counts the number of galaxies and stars in a catalog.
    
    Args:
        cat: The catalog to be counted.

    Returns:
        cat: The catalog with the member count added.
        gal_count: The number of galaxies in the cat.
        star_count: The number of stars in the cat.
    """
    gal_count = len(cat.keys()) - 1
    star_count = 0
    for gal_name in cat:
        if gal_name == META_DATA_KEY:
            continue
        star_count += len(cat[gal_name].keys())

    cat[META_DATA_KEY]['Member count'] = f"{star_count} stars in {gal_count} galaxies."

    return cat, gal_count, star_count


def find_nearest_galaxy(star_coords, catalog = str or dict, ref_catalog = None):
    """Finds the nearest star in a catalog to a given star.
    
    Args:
        star_coords: A dictionary containing the coordinates of the incoming star.
        catalog_path: The path to the catalog file.
        ref_catalog: Reference catalog to cross match with.
    
    Returns:
        nearest_gal: The name of the nearest galaxy.
        gal_dist: The distance between the incoming star and the nearest galaxy.
    """
    # Load JSON file and check type
    print(f"[{datetime.now()}] Finding the nearest galaxy...")
    catalog = catalog_type_check(catalog)

    ref_catalog = catalog_name_check(catalog, ref_catalog)
    # Find the nearest galaxy
    gal_dist = np.inf

    for gal in catalog.keys():
        if gal == META_DATA_KEY:
            continue

        first_star = list(catalog[gal].keys())[0]
        first_star = catalog[gal][first_star][ref_catalog]

        first_star_coord = first_star["RAJ2000"], first_star["DEJ2000"]

        gal_dist_new = (star_coords["RAJ2000"] - first_star_coord[0])**2
        gal_dist_new += (star_coords["DEJ2000"] - first_star_coord[1])**2

        if gal_dist_new < gal_dist:
            gal_dist = gal_dist_new
            nearest_gal = gal

    # Find the nearest galaxy's centroid and boundary,
    # and check if the star is within the boundary
    gal_member_coords = []
    for star in catalog[nearest_gal].keys():
        star = catalog[nearest_gal][star][ref_catalog]
        ra_temp = np.float64(star['RAJ2000'])
        dec_temp = np.float64(star['DEJ2000'])

        gal_member_coords.append([ra_temp, dec_temp])

    ra_, dec_ = np.transpose(gal_member_coords)

    ra_bound = (max(ra_) - min(ra_)) * 0.5
    dec_bound = (max(dec_) - min(dec_)) * 0.5

    # Check if the star is within the boundary
    star_ra, star_dec = star_coords["RAJ2000"], star_coords["DEJ2000"]
    star_dist = (star_ra - (max(ra_) + min(ra_)) * 0.5)**2
    star_dist += (star_dec - (max(dec_) + min(dec_)) * 0.5)**2

    if star_dist > ra_bound**2 + dec_bound**2:
        nearest_gal = None
        gal_dist = None
        time_stamp = datetime.now()
        msg = "Star is not within the boundary of the nearest galaxy, returning None."
        print(f"[{time_stamp}] {msg}")

    return nearest_gal, gal_dist

def galaxy_crossmatch(gal1:dict, gal1_catalog:str, ref_catalog, cache_):
    """See if gal1 is already in the cache. If so, return gal_name. If not,
        return None. Just provide a galaxy in dict format, and the catalog
        it is from.

        This is done by providing a star from gal1, and see if it is within 
        the boundary of any galaxy in the cache.
    
    Args:
        gal1: The galaxy to be crossmatched.
        gal1_catalog: The name of the catalog for gal1.
        ref_catalog: Reference catalog to cross match with.
        cache: The cache to be crossmatched against.
        
    Returns:
        gal_name if gal1 is already in the cache, None otherwise.
        """
    # Provides a star from gal1, and see if it is within the boundary
    # of any galaxy in the cache
    first_star = list(gal1.keys())[0]
    first_star = gal1[first_star][gal1_catalog]
    print(first_star)

    first_star_coord = {"RAJ2000": first_star["RAJ2000"],
                        "DEJ2000": first_star["DEJ2000"]}
    gal_name, _ = find_nearest_galaxy(first_star_coord, cache_, ref_catalog)

    return gal_name


def star_crossmatch(gal1:dict, gal1_catalog:str, gal2:dict, gal2_catalog:str, match_threshold = '1s'):
    """Main function for crossmatching stars between two galaxies in two catalogs.
    
        Precondition: the two galaxies are already crossmatched.

        Args:
            gal1: The incoming galaxy
            gal1_catalog: The catalog of the incoming galaxy
            gal2: The reference galaxy (usually stored in the cache)
            gal2_catalog: The catalog of the reference galaxy
            match_threshold: The threshold for matching stars. Default is 1s, or 1 arcsecond.
                This accepts astropy Angle object, string, or degrees in decimal format in float.

        Returns:
            gal_output: The galaxy to be added to the cache. It should contain 
                stars from both galaxies, with the overlapping stars having 
                two sets of data from the two catalogs.
    """
    # Find the closest star in gal2 for each star in gal1
    # 1. Make a list of all stars in gal1 and gal2
    # 2. For each star in gal2, find the closest star in gal1. Check the distance. If it's too far, skip it.
        # If it's not too far, combine the two star's data and add it to the output galaxy.
    # 3. Whenever there's a match, remove the star from gal1, keep the star in gal2.
    # 4. After iterating through all stars in gal2, add what's left of gal1 to the output galaxy.
    # 5. Add the output galaxy to the cache.
    
    # Check if the threshold is valid
    if isinstance(match_threshold, str):
        match_threshold = Angle(match_threshold).to('deg').value
    elif isinstance(match_threshold, Angle):
        match_threshold = match_threshold.to('deg').value
    elif isinstance(match_threshold, float):
        pass
    else:
        raise TypeError("match_threshold must be a string, an astropy Angle object, or a float.")

    # Convert the stars into SkyCoord objects
    gal1_coords = [] # Incoming data
    for star in gal1.keys():
        star = gal1[star][gal1_catalog]
        ra_temp = np.float64(star['RAJ2000'])
        dec_temp = np.float64(star['DEJ2000'])

        gal1_coords.append([ra_temp, dec_temp])

    gal2_coords = [] # Reference data
    for star in gal2.keys():
        star = gal2[star][gal2_catalog]
        ra_temp = np.float64(star['RAJ2000'])
        dec_temp = np.float64(star['DEJ2000'])

        gal2_coords.append([ra_temp, dec_temp])

    gal1_coords = SkyCoord(gal1_coords, unit="deg")
    gal2_coords = SkyCoord(gal2_coords, unit="deg")

    # Crossmatch the two galaxies
    idx, d2d, _ = match_coordinates_sky(gal1_coords, gal2_coords)
    # idx is the index of the closest star in gal2 for each star in gal1
    # gal2_coords[idx] matches the shape of gal1_coords,
    # # containing gal2 stars that are closest to each gal1 star

    # Initiate the output
    gal_output = gal2.copy()

    idx = np.array(idx) # Represents gal1 using indices of gal2 stars
    d2d = np.array(d2d) # The angles are in degrees in decimal format

    # Produce sort index
    sort_index = np.argsort(idx) # index for sorting idx into ascending order
    idx_sorted = idx[sort_index] # idx but in ascending order
    d2d_sorted = d2d[sort_index]

    # print("idx = ", idx)
    # print("sort_index = ", sort_index)
    # print("idx_sorted = ", idx_sorted)
    # print("d2d_sorted = ", d2d_sorted)

    # Iterate through sorted idx. Group each identical idx into one list,
    # # and find the one with the smallest d2d.
    # The one with the smallest d2d is the closest star.
    # The other ones are flagged as new stars
    # If the d2d is too large, then the star is flagged as a new star
    duplicate_flag = False
    match_list = {}
    for count, indx in enumerate(idx_sorted):
        dist_temp = d2d_sorted[count]

        if indx != idx_sorted[count - 1]:
            # If the current indx is not equal to the previous indx, make a new minor list
            count_start = count
            idx_list = [indx]
            dist_list = [dist_temp]
            temp_list_indx = [count]
            duplicate_flag = False
        else:
            # If the current indx is equal to the previous indx, append it to the minor list
            idx_list.append(indx)
            dist_list = np.append(dist_list, dist_temp)
            temp_list_indx.append(count)
            duplicate_flag = True

        if duplicate_flag is False and count != 0:
            # If the current indx is not equal to the previous indx, and it's not the first indx
            # Identify the nearest star in the minor list, compare its distance against threshold
            dist_list = np.array(dist_list)
            nearest_temp = np.argmin(dist_list) # Index of the nearest star in the minor list
            nearest = nearest_temp + count_start # Index of the nearest star in idx_sorted.

            idx_nearest = sort_index[nearest] # index of nearest in idx
            dist_nearest = dist_list[nearest_temp] # distance of nearest

            # Confirm match if the distance is within the threshold
            if dist_nearest <= match_threshold:
                ga1_names = list(gal1.keys())
                ga2_names = list(gal2.keys())
                match_list[ga1_names[idx_nearest]] = ga2_names[idx[idx_nearest]]

    for star1_name in gal1.keys():
        # Iterate through each star in gal1, 
        # # if there's a match in gal2, add the data from gal1 to gal2.
        # # if there's no match in gal2, add the star directly to gal_output.
        if star1_name in match_list.keys():
            star2_name = match_list[star1_name]
            gal_output[star2_name][gal1_catalog] = gal1[star1_name][gal1_catalog]
        
        else:
            gal_output[star1_name] = gal1[star1_name]

    return gal_output

# Test the functions
if __name__ == "__main__":
    # Load catalog and cache
    catalog_ = json.load(open("Temp/Reighert 2020.json", encoding="utf-8"))
    cache = json.load(open("Data/cache.json", encoding="utf-8"))

    gal_1 = catalog_['Scl']
    gal_2 = cache['Scl']

    # gal1_, gal2_ = star_crossmatch(gal1, "J/ApJS/191/352/abun", gal2, "J/ApJS/191/352/abun")
    star_crossmatch(gal_1, "J/A+A/641/A127", gal_2, "J/ApJS/191/352/abun")

