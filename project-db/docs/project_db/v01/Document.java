/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Documents (references — actual files stay in Drive / CompanyCam / etc.)
 * -----------------------------------------------------------------------------
 * Document carries optional FKs to several possible "attachables". A cleaner
 * long-term shape is a polymorphic Attachable abstraction, but for v0.1 the
 * fan-out of optionals is more readable and translates 1:1 to SQL nullable
 * FKs.
 */
// line 303 "../../model-v0.1.ump"
public class Document extends CanonicalEntity
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Document Attributes
  private String name;
  private String mimeType;
  private String url;
  private String storageRef;

  //Document Associations
  private Project project;
  private Deal deal;
  private Client client;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Document(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, String aUrl)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    mimeType = null;
    url = aUrl;
    storageRef = null;
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setName(String aName)
  {
    boolean wasSet = false;
    name = aName;
    wasSet = true;
    return wasSet;
  }

  public boolean setMimeType(String aMimeType)
  {
    boolean wasSet = false;
    mimeType = aMimeType;
    wasSet = true;
    return wasSet;
  }

  public boolean setUrl(String aUrl)
  {
    boolean wasSet = false;
    url = aUrl;
    wasSet = true;
    return wasSet;
  }

  public boolean setStorageRef(String aStorageRef)
  {
    boolean wasSet = false;
    storageRef = aStorageRef;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  public String getMimeType()
  {
    return mimeType;
  }

  /**
   * canonical URL to the file
   */
  public String getUrl()
  {
    return url;
  }

  /**
   * source-specific reference
   */
  public String getStorageRef()
  {
    return storageRef;
  }
  /* Code from template association_GetOne */
  public Project getProject()
  {
    return project;
  }

  public boolean hasProject()
  {
    boolean has = project != null;
    return has;
  }
  /* Code from template association_GetOne */
  public Deal getDeal()
  {
    return deal;
  }

  public boolean hasDeal()
  {
    boolean has = deal != null;
    return has;
  }
  /* Code from template association_GetOne */
  public Client getClient()
  {
    return client;
  }

  public boolean hasClient()
  {
    boolean has = client != null;
    return has;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setProject(Project aProject)
  {
    boolean wasSet = false;
    Project existingProject = project;
    project = aProject;
    if (existingProject != null && !existingProject.equals(aProject))
    {
      existingProject.removeDocument(this);
    }
    if (aProject != null)
    {
      aProject.addDocument(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setDeal(Deal aDeal)
  {
    boolean wasSet = false;
    Deal existingDeal = deal;
    deal = aDeal;
    if (existingDeal != null && !existingDeal.equals(aDeal))
    {
      existingDeal.removeDocument(this);
    }
    if (aDeal != null)
    {
      aDeal.addDocument(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setClient(Client aClient)
  {
    boolean wasSet = false;
    Client existingClient = client;
    client = aClient;
    if (existingClient != null && !existingClient.equals(aClient))
    {
      existingClient.removeDocument(this);
    }
    if (aClient != null)
    {
      aClient.addDocument(this);
    }
    wasSet = true;
    return wasSet;
  }

  public void delete()
  {
    if (project != null)
    {
      Project placeholderProject = project;
      this.project = null;
      placeholderProject.removeDocument(this);
    }
    if (deal != null)
    {
      Deal placeholderDeal = deal;
      this.deal = null;
      placeholderDeal.removeDocument(this);
    }
    if (client != null)
    {
      Client placeholderClient = client;
      this.client = null;
      placeholderClient.removeDocument(this);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "mimeType" + ":" + getMimeType()+ "," +
            "url" + ":" + getUrl()+ "," +
            "storageRef" + ":" + getStorageRef()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "project = "+(getProject()!=null?Integer.toHexString(System.identityHashCode(getProject())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "deal = "+(getDeal()!=null?Integer.toHexString(System.identityHashCode(getDeal())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "client = "+(getClient()!=null?Integer.toHexString(System.identityHashCode(getClient())):"null");
  }
}