/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;

/**
 * One canonical entity owns many external IDs (one per source system it lives
 * in). Composition: when a canonical entity is purged, its mappings go too —
 * orphaned mapping rows are meaningless.
 * 
 * Composite key prevents duplicate mappings: the same external key string
 * can legitimately appear across systems (Monday board id 12345 and a
 * QuickBooks customer id 12345 are unrelated), and even within one system
 * across different entity types — so all three columns must match for a
 * row to be a duplicate.
 */
// line 101 "../../model-v0.1.ump"
public class ExternalId
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum SourceSystem { MONDAY, COMPANYCAM, QUICKBOOKS, GOOGLE_DRIVE, INTERNAL }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //ExternalId Attributes
  private SourceSystem source;
  private String externalKey;
  private String externalUrl;
  private String entityType;
  private DateTime lastSyncedAt;
  private String rawPayloadHash;

  //ExternalId Associations
  private CanonicalEntity canonicalEntity;

  //Helper Variables
  private int cachedHashCode;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public ExternalId(SourceSystem aSource, String aExternalKey, String aEntityType, DateTime aLastSyncedAt, CanonicalEntity aCanonicalEntity)
  {
    cachedHashCode = -1;
    source = aSource;
    externalKey = aExternalKey;
    externalUrl = null;
    entityType = aEntityType;
    lastSyncedAt = aLastSyncedAt;
    rawPayloadHash = null;
    boolean didAddCanonicalEntity = setCanonicalEntity(aCanonicalEntity);
    if (!didAddCanonicalEntity)
    {
      throw new RuntimeException("Unable to create externalId due to canonicalEntity. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setExternalUrl(String aExternalUrl)
  {
    boolean wasSet = false;
    externalUrl = aExternalUrl;
    wasSet = true;
    return wasSet;
  }

  public boolean setLastSyncedAt(DateTime aLastSyncedAt)
  {
    boolean wasSet = false;
    lastSyncedAt = aLastSyncedAt;
    wasSet = true;
    return wasSet;
  }

  public boolean setRawPayloadHash(String aRawPayloadHash)
  {
    boolean wasSet = false;
    rawPayloadHash = aRawPayloadHash;
    wasSet = true;
    return wasSet;
  }

  public SourceSystem getSource()
  {
    return source;
  }

  /**
   * the ID in that source system
   */
  public String getExternalKey()
  {
    return externalKey;
  }

  /**
   * deep link back to the source record
   */
  public String getExternalUrl()
  {
    return externalUrl;
  }

  /**
   * canonical class name, e.g. "Project"
   */
  public String getEntityType()
  {
    return entityType;
  }

  public DateTime getLastSyncedAt()
  {
    return lastSyncedAt;
  }

  /**
   * detect upstream changes cheaply
   */
  public String getRawPayloadHash()
  {
    return rawPayloadHash;
  }
  /* Code from template association_GetOne */
  public CanonicalEntity getCanonicalEntity()
  {
    return canonicalEntity;
  }
  /* Code from template association_SetOneToMany */
  public boolean setCanonicalEntity(CanonicalEntity aCanonicalEntity)
  {
    boolean wasSet = false;
    if (aCanonicalEntity == null)
    {
      return wasSet;
    }

    CanonicalEntity existingCanonicalEntity = canonicalEntity;
    canonicalEntity = aCanonicalEntity;
    if (existingCanonicalEntity != null && !existingCanonicalEntity.equals(aCanonicalEntity))
    {
      existingCanonicalEntity.removeExternalId(this);
    }
    canonicalEntity.addExternalId(this);
    wasSet = true;
    return wasSet;
  }

  public boolean equals(Object obj)
  {
    if (obj == null) { return false; }
    if (!getClass().equals(obj.getClass())) { return false; }

    ExternalId compareTo = (ExternalId)obj;
  
    if (getSource() == null && compareTo.getSource() != null)
    {
      return false;
    }
    else if (getSource() != null && !getSource().equals(compareTo.getSource()))
    {
      return false;
    }

    if (getExternalKey() == null && compareTo.getExternalKey() != null)
    {
      return false;
    }
    else if (getExternalKey() != null && !getExternalKey().equals(compareTo.getExternalKey()))
    {
      return false;
    }

    if (getEntityType() == null && compareTo.getEntityType() != null)
    {
      return false;
    }
    else if (getEntityType() != null && !getEntityType().equals(compareTo.getEntityType()))
    {
      return false;
    }

    return true;
  }

  public int hashCode()
  {
    if (cachedHashCode != -1)
    {
      return cachedHashCode;
    }
    cachedHashCode = 17;
    if (getSource() != null)
    {
      cachedHashCode = cachedHashCode * 23 + getSource().hashCode();
    }
    else
    {
      cachedHashCode = cachedHashCode * 23;
    }

    if (getExternalKey() != null)
    {
      cachedHashCode = cachedHashCode * 23 + getExternalKey().hashCode();
    }
    else
    {
      cachedHashCode = cachedHashCode * 23;
    }

    if (getEntityType() != null)
    {
      cachedHashCode = cachedHashCode * 23 + getEntityType().hashCode();
    }
    else
    {
      cachedHashCode = cachedHashCode * 23;
    }

    
    return cachedHashCode;
  }

  public void delete()
  {
    CanonicalEntity placeholderCanonicalEntity = canonicalEntity;
    this.canonicalEntity = null;
    if(placeholderCanonicalEntity != null)
    {
      placeholderCanonicalEntity.removeExternalId(this);
    }
  }


  public String toString()
  {
    return super.toString() + "["+
            "entityType" + ":" + getEntityType()+ "," +
            "externalKey" + ":" + getExternalKey()+ "," +
            "externalUrl" + ":" + getExternalUrl()+ "," +
            "rawPayloadHash" + ":" + getRawPayloadHash()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "source" + "=" + (getSource() != null ? !getSource().equals(this)  ? getSource().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "lastSyncedAt" + "=" + (getLastSyncedAt() != null ? !getLastSyncedAt().equals(this)  ? getLastSyncedAt().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "canonicalEntity = "+(getCanonicalEntity()!=null?Integer.toHexString(System.identityHashCode(getCanonicalEntity())):"null");
  }
}