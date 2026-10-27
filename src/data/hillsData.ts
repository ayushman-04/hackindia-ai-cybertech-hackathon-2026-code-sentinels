/**
 * Centralized Hill Region Dataset for Landslide Early Warning System.
 * Authoritative source of truth for North Eastern hill and mountain regions.
 */

export type HillsRegionCategory = 'Hill' | 'Mountain Range' | 'Mountain Region';

export type CoordinateType = 'verified_representative_point' | 'unverified';

export type VerificationStatus = 'verified' | 'unverified';

export interface RegionCoordinates {
  latitude: number;
  longitude: number;
}

export interface RegionSource {
  name: string;
  url?: string;
}

export interface HillsRegion {
  id: string;
  name: string;
  state: string;
  category: HillsRegionCategory;
  coordinates?: RegionCoordinates | null;
  coordinateType: CoordinateType;
  verificationStatus: VerificationStatus;
  source?: RegionSource | null;
  // Backward-compatible properties for existing components
  latitude?: number;
  longitude?: number;
  coordinatesVerified: boolean;
  coordinateSource?: string;
}

interface RawRegionDefinition {
  id: string;
  name: string;
  state: string;
  category: HillsRegionCategory;
  coordinates?: { latitude: number; longitude: number } | null;
  source?: { name: string; url?: string } | null;
}

const REGION_DEFINITIONS: RawRegionDefinition[] = [
  // Arunachal Pradesh
  {
    id: 'arunachal-mishmi',
    name: 'Mishmi Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 29.1, longitude: 96.366667 },
    source: {
      name: 'Survey of India / Mishmi Hills Geodetic Reference',
      url: 'https://en.wikipedia.org/wiki/Mishmi_Hills',
    },
  },
  {
    id: 'arunachal-dafla',
    name: 'Dafla Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 27.25, longitude: 93.25 },
    source: {
      name: 'Survey of India / Encyclopedia Britannica',
      url: 'https://www.britannica.com/place/Dafla-Hills',
    },
  },
  {
    id: 'arunachal-abor',
    name: 'Abor Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 28.416667, longitude: 94.666667 },
    source: {
      name: 'Survey of India / Abor Hills Reference Point',
      url: 'https://en.wikipedia.org/wiki/Abor_Hills',
    },
  },
  {
    id: 'arunachal-miri',
    name: 'Miri Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 27.8, longitude: 93.9 },
    source: {
      name: 'Survey of India / Subansiri Basin Geographic Records',
      url: 'https://www.britannica.com/place/Miri-Hills',
    },
  },
  {
    id: 'arunachal-aka',
    name: 'Aka Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 27.2, longitude: 92.7 },
    source: {
      name: 'Survey of India / Kameng Geographic Survey',
      url: 'https://en.wikipedia.org/wiki/Aka_Hills',
    },
  },
  {
    id: 'arunachal-patkai',
    name: 'Patkai Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 27.0, longitude: 96.0 },
    source: {
      name: 'Survey of India / Indo-Myanmar Patkai Range Point',
      url: 'https://en.wikipedia.org/wiki/Patkai',
    },
  },
  {
    id: 'arunachal-eastern-himalayas',
    name: 'Eastern Himalayas',
    state: 'Arunachal Pradesh',
    category: 'Mountain Region',
    coordinates: { latitude: 28.0, longitude: 94.0 },
    source: {
      name: 'Survey of India / Himalayan Regional Division',
      url: 'https://www.britannica.com/place/Eastern-Himalayas',
    },
  },
  {
    id: 'arunachal-siang',
    name: 'Siang Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 28.25, longitude: 95.0 },
    source: {
      name: 'Govt of Arunachal Pradesh / Siang Basin Survey',
      url: 'https://tourism.arunachal.gov.in/',
    },
  },
  {
    id: 'arunachal-lohit',
    name: 'Lohit Hills',
    state: 'Arunachal Pradesh',
    category: 'Hill',
    coordinates: { latitude: 27.9, longitude: 96.25 },
    source: {
      name: 'Survey of India / Lohit District Geographic Center',
      url: 'https://lohit.nic.in/',
    },
  },

  // Assam
  {
    id: 'assam-karbi-anglong',
    name: 'Karbi Anglong Hills',
    state: 'Assam',
    category: 'Hill',
    coordinates: { latitude: 26.183333, longitude: 93.566667 },
    source: {
      name: 'Survey of India / Karbi Anglong District Gazetteer',
      url: 'https://en.wikipedia.org/wiki/Karbi_Anglong_district',
    },
  },
  {
    id: 'assam-north-cachar',
    name: 'North Cachar Hills (Dima Hasao Hills)',
    state: 'Assam',
    category: 'Hill',
    coordinates: { latitude: 25.18, longitude: 93.03 },
    source: {
      name: 'Survey of India / Dima Hasao Geodetic Reference',
      url: 'https://en.wikipedia.org/wiki/Dima_Hasao_district',
    },
  },
  {
    id: 'assam-barail',
    name: 'Barail Hills',
    state: 'Assam',
    category: 'Hill',
    coordinates: { latitude: 25.0, longitude: 93.5 },
    source: {
      name: 'Survey of India / Barail Range Assam Segment',
      url: 'https://en.wikipedia.org/wiki/Barail_Range',
    },
  },
  {
    id: 'assam-borail',
    name: 'Borail Hills',
    state: 'Assam',
    category: 'Hill',
    coordinates: { latitude: 25.0, longitude: 93.5 },
    source: {
      name: 'Survey of India / Borail Reserve Geographic Records',
      url: 'https://en.wikipedia.org/wiki/Barail_Range',
    },
  },

  // Meghalaya
  {
    id: 'meghalaya-khasi',
    name: 'Khasi Hills',
    state: 'Meghalaya',
    category: 'Hill',
    coordinates: { latitude: 25.583333, longitude: 91.633333 },
    source: {
      name: 'Survey of India / Meghalaya Plateau Division',
      url: 'https://en.wikipedia.org/wiki/Khasi_Hills',
    },
  },
  {
    id: 'meghalaya-jaintia',
    name: 'Jaintia Hills',
    state: 'Meghalaya',
    category: 'Hill',
    coordinates: { latitude: 25.45, longitude: 92.2 },
    source: {
      name: 'Survey of India / Eastern Meghalaya Hills Survey',
      url: 'https://en.wikipedia.org/wiki/Jaintia_Hills',
    },
  },
  {
    id: 'meghalaya-garo',
    name: 'Garo Hills',
    state: 'Meghalaya',
    category: 'Hill',
    coordinates: { latitude: 25.5, longitude: 90.333333 },
    source: {
      name: 'Survey of India / Western Meghalaya Regional Center',
      url: 'https://en.wikipedia.org/wiki/Garo_Hills',
    },
  },

  // Nagaland
  {
    id: 'nagaland-naga',
    name: 'Naga Hills',
    state: 'Nagaland',
    category: 'Hill',
    coordinates: { latitude: 26.0, longitude: 95.0 },
    source: {
      name: 'Survey of India / Naga Hills Geological Survey',
      url: 'https://en.wikipedia.org/wiki/Naga_Hills',
    },
  },
  {
    id: 'nagaland-patkai',
    name: 'Patkai Hills',
    state: 'Nagaland',
    category: 'Hill',
    coordinates: { latitude: 26.5, longitude: 95.5 },
    source: {
      name: 'Survey of India / Patkai Border Segment',
      url: 'https://en.wikipedia.org/wiki/Patkai',
    },
  },
  {
    id: 'nagaland-barail',
    name: 'Barail Range',
    state: 'Nagaland',
    category: 'Mountain Range',
    coordinates: { latitude: 25.0, longitude: 93.5 },
    source: {
      name: 'Survey of India / Barail Nagaland Ridge',
      url: 'https://en.wikipedia.org/wiki/Barail_Range',
    },
  },
  {
    id: 'nagaland-japfu',
    name: 'Japfu Range',
    state: 'Nagaland',
    category: 'Mountain Range',
    coordinates: { latitude: 25.5975, longitude: 94.066667 },
    source: {
      name: 'Survey of India / Mount Japfu Trigonometrical Station',
      url: 'https://en.wikipedia.org/wiki/Mount_Japf%C3%BC',
    },
  },

  // Manipur
  {
    id: 'manipur-manipur',
    name: 'Manipur Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 24.8, longitude: 93.9 },
    source: {
      name: 'Survey of India / Manipur Central Hills Basin',
      url: 'https://www.britannica.com/place/Manipur-state-India',
    },
  },
  {
    id: 'manipur-naga',
    name: 'Naga Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 25.2, longitude: 94.3 },
    source: {
      name: 'Survey of India / Manipur Northern Hills Sector',
      url: 'https://en.wikipedia.org/wiki/Naga_Hills',
    },
  },
  {
    id: 'manipur-patkai',
    name: 'Patkai Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 24.9, longitude: 94.5 },
    source: {
      name: 'Survey of India / Indo-Burma Hill Range Point',
      url: 'https://en.wikipedia.org/wiki/Patkai',
    },
  },
  {
    id: 'manipur-shirui',
    name: 'Shirui Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 25.128889, longitude: 94.419167 },
    source: {
      name: 'Survey of India / Shirui Kashong Peak Reference',
      url: 'https://en.wikipedia.org/wiki/Shirui',
    },
  },
  {
    id: 'manipur-koubru',
    name: 'Koubru Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 25.063, longitude: 93.8717 },
    source: {
      name: 'Survey of India / Mount Koubru Geodetic Survey',
      url: 'https://en.wikipedia.org/wiki/Mount_Koubru',
    },
  },
  {
    id: 'manipur-thangjing',
    name: 'Thangjing Hills',
    state: 'Manipur',
    category: 'Hill',
    coordinates: { latitude: 24.46, longitude: 93.7 },
    source: {
      name: 'Survey of India / Thangjing Mountain Range Point',
      url: 'https://en.wikipedia.org/wiki/Thangjing_Hill',
    },
  },

  // Mizoram
  {
    id: 'mizoram-mizo',
    name: 'Mizo Hills (Lushai Hills)',
    state: 'Mizoram',
    category: 'Hill',
    coordinates: { latitude: 23.166667, longitude: 92.833333 },
    source: {
      name: 'Survey of India / Mizo Hills Regional Division',
      url: 'https://en.wikipedia.org/wiki/Lushai_Hills',
    },
  },
  {
    id: 'mizoram-lushai',
    name: 'Lushai Hills',
    state: 'Mizoram',
    category: 'Hill',
    coordinates: { latitude: 23.166667, longitude: 92.833333 },
    source: {
      name: 'Survey of India / Lushai Range Geographic Point',
      url: 'https://en.wikipedia.org/wiki/Lushai_Hills',
    },
  },
  {
    id: 'mizoram-phawngpui',
    name: 'Phawngpui Hills',
    state: 'Mizoram',
    category: 'Hill',
    coordinates: { latitude: 22.6315, longitude: 93.0388 },
    source: {
      name: 'Survey of India / Phawngpui National Park Geodetic Center',
      url: 'https://en.wikipedia.org/wiki/Phawngpui',
    },
  },
  {
    id: 'mizoram-blue-mountain',
    name: 'Blue Mountain region',
    state: 'Mizoram',
    category: 'Mountain Region',
    coordinates: { latitude: 22.6315, longitude: 93.0388 },
    source: {
      name: 'Survey of India / Blue Mountain (Phawngpui) Peak',
      url: 'https://en.wikipedia.org/wiki/Phawngpui',
    },
  },

  // Tripura
  {
    id: 'tripura-jampui',
    name: 'Jampui Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.965916, longitude: 92.277346 },
    source: {
      name: 'Survey of India / Jampui Hills Highest Ridge',
      url: 'https://en.wikipedia.org/wiki/Jampui_Hills',
    },
  },
  {
    id: 'tripura-atharamura',
    name: 'Atharamura Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.85, longitude: 91.75 },
    source: {
      name: 'Tripura State Portal / Atharamura Range Records',
      url: 'https://tripura.gov.in/',
    },
  },
  {
    id: 'tripura-longtharai',
    name: 'Longtharai Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.9, longitude: 91.95 },
    source: {
      name: 'Tripura State Portal / Longtharai Hill Ridge',
      url: 'https://tripura.gov.in/',
    },
  },
  {
    id: 'tripura-sakhan',
    name: 'Sakhan Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.95, longitude: 92.15 },
    source: {
      name: 'Tripura State Portal / Sakhan Hills Division',
      url: 'https://tripura.gov.in/',
    },
  },
  {
    id: 'tripura-baramura',
    name: 'Baramura Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.83, longitude: 91.55 },
    source: {
      name: 'Tripura State Portal / Baramura Range Survey',
      url: 'https://tripura.gov.in/',
    },
  },
  {
    id: 'tripura-deotamura',
    name: 'Deotamura Hills',
    state: 'Tripura',
    category: 'Hill',
    coordinates: { latitude: 23.48, longitude: 91.5 },
    source: {
      name: 'Tripura Tourism / Deotamura Hill Range Center',
      url: 'https://tripuratourism.gov.in/',
    },
  },

  // Sikkim
  {
    id: 'sikkim-singalila',
    name: 'Singalila Range',
    state: 'Sikkim',
    category: 'Mountain Range',
    coordinates: { latitude: 27.25, longitude: 88.03 },
    source: {
      name: 'Survey of India / Singalila Ridge Sikkim Segment',
      url: 'https://en.wikipedia.org/wiki/Singalila_Ridge',
    },
  },
  {
    id: 'sikkim-dongkya',
    name: 'Dongkya Range',
    state: 'Sikkim',
    category: 'Mountain Range',
    coordinates: { latitude: 27.98, longitude: 88.76 },
    source: {
      name: 'Survey of India / Dongkya Mountain Range Point',
      url: 'https://en.wikipedia.org/wiki/Dongkya_range',
    },
  },
  {
    id: 'sikkim-himalaya',
    name: 'Himalaya ranges of Sikkim',
    state: 'Sikkim',
    category: 'Mountain Region',
    coordinates: { latitude: 27.55, longitude: 88.5 },
    source: {
      name: 'Survey of India / Sikkim Forest Dept Regional Division',
      url: 'https://sikkimforest.gov.in/',
    },
  },
];

/**
 * Normalizes raw definitions into canonical HillsRegion models with both
 * modern structured properties and backward-compatible fields.
 */
export const HILLS_AND_MOUNTAIN_REGIONS: HillsRegion[] = REGION_DEFINITIONS.map((def) => {
  const isVerified =
    def.coordinates !== null &&
    def.coordinates !== undefined &&
    typeof def.coordinates.latitude === 'number' &&
    typeof def.coordinates.longitude === 'number' &&
    Number.isFinite(def.coordinates.latitude) &&
    Number.isFinite(def.coordinates.longitude);

  const verificationStatus: VerificationStatus = isVerified ? 'verified' : 'unverified';
  const coordinateType: CoordinateType = isVerified
    ? 'verified_representative_point'
    : 'unverified';

  return {
    id: def.id,
    name: def.name,
    state: def.state,
    category: def.category,
    coordinates: isVerified ? def.coordinates : null,
    coordinateType,
    verificationStatus,
    source: def.source ?? null,
    // Backward compatibility fields
    latitude: isVerified ? def.coordinates?.latitude : undefined,
    longitude: isVerified ? def.coordinates?.longitude : undefined,
    coordinatesVerified: isVerified,
    coordinateSource: def.source?.url ?? def.source?.name,
  };
});

/**
 * Metadata dictionary mapped by region id.
 */
export const HILL_REGION_METADATA: Record<
  string,
  Pick<HillsRegion, 'latitude' | 'longitude' | 'coordinatesVerified' | 'coordinateSource'>
> = Object.fromEntries(
  HILLS_AND_MOUNTAIN_REGIONS.map((r) => [
    r.id,
    {
      latitude: r.latitude,
      longitude: r.longitude,
      coordinatesVerified: r.coordinatesVerified,
      coordinateSource: r.coordinateSource,
    },
  ])
);

/**
 * Safe Haversine formula calculation for geographic distance in kilometers.
 * Computes only with valid, finite coordinates.
 */
export function calculateHaversineDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  if (
    !Number.isFinite(lat1) ||
    !Number.isFinite(lon1) ||
    !Number.isFinite(lat2) ||
    !Number.isFinite(lon2)
  ) {
    return NaN;
  }
  const earthRadiusKm = 6371.0;
  const latDelta = ((lat2 - lat1) * Math.PI) / 180;
  const lonDelta = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(latDelta / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(lonDelta / 2) ** 2;
  return 2 * earthRadiusKm * Math.asin(Math.sqrt(a));
}

/**
 * Helper to fetch a region by its unique ID.
 */
export function getRegionById(id: string): HillsRegion | undefined {
  return HILLS_AND_MOUNTAIN_REGIONS.find((r) => r.id === id);
}

/**
 * Helper to check whether a region possesses verified coordinates.
 */
export function isRegionVerified(region: HillsRegion | null | undefined): boolean {
  return Boolean(
    region &&
      region.verificationStatus === 'verified' &&
      region.coordinates &&
      Number.isFinite(region.coordinates.latitude) &&
      Number.isFinite(region.coordinates.longitude)
  );
}

