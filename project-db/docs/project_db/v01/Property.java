/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Real estate
 * -----------------------------------------------------------------------------
 */
// line 168 "../../model-v0.1.ump"
public class Property extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum ProjectStatus { PROPOSED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED }
  public enum LeadStage { NEW, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Property Attributes
  private String address;
  private String shortLabel;
  private String city;
  private String region;
  private String postalCode;
  private String country;
  private String propertyType;
  private float lotSize;
  private int yearBuilt;

  //Property Associations
  private Organization organization;
  private List<Lead> leads;
  private List<Deal> deals;
  private List<Project> projects;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Property(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aAddress, Organization aOrganization)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    address = aAddress;
    shortLabel = null;
    city = null;
    region = null;
    postalCode = null;
    country = null;
    propertyType = null;
    lotSize = 0.0f;
    yearBuilt = 0;
    boolean didAddOrganization = setOrganization(aOrganization);
    if (!didAddOrganization)
    {
      throw new RuntimeException("Unable to create property due to organization. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    leads = new ArrayList<Lead>();
    deals = new ArrayList<Deal>();
    projects = new ArrayList<Project>();
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setAddress(String aAddress)
  {
    boolean wasSet = false;
    address = aAddress;
    wasSet = true;
    return wasSet;
  }

  public boolean setShortLabel(String aShortLabel)
  {
    boolean wasSet = false;
    shortLabel = aShortLabel;
    wasSet = true;
    return wasSet;
  }

  public boolean setCity(String aCity)
  {
    boolean wasSet = false;
    city = aCity;
    wasSet = true;
    return wasSet;
  }

  public boolean setRegion(String aRegion)
  {
    boolean wasSet = false;
    region = aRegion;
    wasSet = true;
    return wasSet;
  }

  public boolean setPostalCode(String aPostalCode)
  {
    boolean wasSet = false;
    postalCode = aPostalCode;
    wasSet = true;
    return wasSet;
  }

  public boolean setCountry(String aCountry)
  {
    boolean wasSet = false;
    country = aCountry;
    wasSet = true;
    return wasSet;
  }

  public boolean setPropertyType(String aPropertyType)
  {
    boolean wasSet = false;
    propertyType = aPropertyType;
    wasSet = true;
    return wasSet;
  }

  public boolean setLotSize(float aLotSize)
  {
    boolean wasSet = false;
    lotSize = aLotSize;
    wasSet = true;
    return wasSet;
  }

  public boolean setYearBuilt(int aYearBuilt)
  {
    boolean wasSet = false;
    yearBuilt = aYearBuilt;
    wasSet = true;
    return wasSet;
  }

  public String getAddress()
  {
    return address;
  }

  /**
   * e.g. "923 Rockland"
   */
  public String getShortLabel()
  {
    return shortLabel;
  }

  public String getCity()
  {
    return city;
  }

  public String getRegion()
  {
    return region;
  }

  public String getPostalCode()
  {
    return postalCode;
  }

  public String getCountry()
  {
    return country;
  }

  /**
   * residential, commercial, mixed, ...
   */
  public String getPropertyType()
  {
    return propertyType;
  }

  public float getLotSize()
  {
    return lotSize;
  }

  public int getYearBuilt()
  {
    return yearBuilt;
  }
  /* Code from template association_GetOne */
  public Organization getOrganization()
  {
    return organization;
  }
  /* Code from template association_GetMany */
  public Lead getLead(int index)
  {
    Lead aLead = leads.get(index);
    return aLead;
  }

  public List<Lead> getLeads()
  {
    List<Lead> newLeads = Collections.unmodifiableList(leads);
    return newLeads;
  }

  public int numberOfLeads()
  {
    int number = leads.size();
    return number;
  }

  public boolean hasLeads()
  {
    boolean has = leads.size() > 0;
    return has;
  }

  public int indexOfLead(Lead aLead)
  {
    int index = leads.indexOf(aLead);
    return index;
  }
  /* Code from template association_GetMany */
  public Deal getDeal(int index)
  {
    Deal aDeal = deals.get(index);
    return aDeal;
  }

  public List<Deal> getDeals()
  {
    List<Deal> newDeals = Collections.unmodifiableList(deals);
    return newDeals;
  }

  public int numberOfDeals()
  {
    int number = deals.size();
    return number;
  }

  public boolean hasDeals()
  {
    boolean has = deals.size() > 0;
    return has;
  }

  public int indexOfDeal(Deal aDeal)
  {
    int index = deals.indexOf(aDeal);
    return index;
  }
  /* Code from template association_GetMany */
  public Project getProject(int index)
  {
    Project aProject = projects.get(index);
    return aProject;
  }

  public List<Project> getProjects()
  {
    List<Project> newProjects = Collections.unmodifiableList(projects);
    return newProjects;
  }

  public int numberOfProjects()
  {
    int number = projects.size();
    return number;
  }

  public boolean hasProjects()
  {
    boolean has = projects.size() > 0;
    return has;
  }

  public int indexOfProject(Project aProject)
  {
    int index = projects.indexOf(aProject);
    return index;
  }
  /* Code from template association_SetOneToMany */
  public boolean setOrganization(Organization aOrganization)
  {
    boolean wasSet = false;
    if (aOrganization == null)
    {
      return wasSet;
    }

    Organization existingOrganization = organization;
    organization = aOrganization;
    if (existingOrganization != null && !existingOrganization.equals(aOrganization))
    {
      existingOrganization.removeProperty(this);
    }
    organization.addProperty(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfLeads()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addLead(Lead aLead)
  {
    boolean wasAdded = false;
    if (leads.contains(aLead)) { return false; }
    Property existingProperty = aLead.getProperty();
    if (existingProperty == null)
    {
      aLead.setProperty(this);
    }
    else if (!this.equals(existingProperty))
    {
      existingProperty.removeLead(aLead);
      addLead(aLead);
    }
    else
    {
      leads.add(aLead);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeLead(Lead aLead)
  {
    boolean wasRemoved = false;
    if (leads.contains(aLead))
    {
      leads.remove(aLead);
      aLead.setProperty(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addLeadAt(Lead aLead, int index)
  {  
    boolean wasAdded = false;
    if(addLead(aLead))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfLeads()) { index = numberOfLeads() - 1; }
      leads.remove(aLead);
      leads.add(index, aLead);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveLeadAt(Lead aLead, int index)
  {
    boolean wasAdded = false;
    if(leads.contains(aLead))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfLeads()) { index = numberOfLeads() - 1; }
      leads.remove(aLead);
      leads.add(index, aLead);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addLeadAt(aLead, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfDeals()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addDeal(Deal aDeal)
  {
    boolean wasAdded = false;
    if (deals.contains(aDeal)) { return false; }
    Property existingProperty = aDeal.getProperty();
    if (existingProperty == null)
    {
      aDeal.setProperty(this);
    }
    else if (!this.equals(existingProperty))
    {
      existingProperty.removeDeal(aDeal);
      addDeal(aDeal);
    }
    else
    {
      deals.add(aDeal);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeDeal(Deal aDeal)
  {
    boolean wasRemoved = false;
    if (deals.contains(aDeal))
    {
      deals.remove(aDeal);
      aDeal.setProperty(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addDealAt(Deal aDeal, int index)
  {  
    boolean wasAdded = false;
    if(addDeal(aDeal))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDeals()) { index = numberOfDeals() - 1; }
      deals.remove(aDeal);
      deals.add(index, aDeal);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveDealAt(Deal aDeal, int index)
  {
    boolean wasAdded = false;
    if(deals.contains(aDeal))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDeals()) { index = numberOfDeals() - 1; }
      deals.remove(aDeal);
      deals.add(index, aDeal);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addDealAt(aDeal, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfProjects()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addProject(Project aProject)
  {
    boolean wasAdded = false;
    if (projects.contains(aProject)) { return false; }
    Property existingProperty = aProject.getProperty();
    if (existingProperty == null)
    {
      aProject.setProperty(this);
    }
    else if (!this.equals(existingProperty))
    {
      existingProperty.removeProject(aProject);
      addProject(aProject);
    }
    else
    {
      projects.add(aProject);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeProject(Project aProject)
  {
    boolean wasRemoved = false;
    if (projects.contains(aProject))
    {
      projects.remove(aProject);
      aProject.setProperty(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addProjectAt(Project aProject, int index)
  {  
    boolean wasAdded = false;
    if(addProject(aProject))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfProjects()) { index = numberOfProjects() - 1; }
      projects.remove(aProject);
      projects.add(index, aProject);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveProjectAt(Project aProject, int index)
  {
    boolean wasAdded = false;
    if(projects.contains(aProject))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfProjects()) { index = numberOfProjects() - 1; }
      projects.remove(aProject);
      projects.add(index, aProject);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addProjectAt(aProject, index);
    }
    return wasAdded;
  }

  public void delete()
  {
    Organization placeholderOrganization = organization;
    this.organization = null;
    if(placeholderOrganization != null)
    {
      placeholderOrganization.removeProperty(this);
    }
    while( !leads.isEmpty() )
    {
      leads.get(0).setProperty(null);
    }
    while( !deals.isEmpty() )
    {
      deals.get(0).setProperty(null);
    }
    while( !projects.isEmpty() )
    {
      projects.get(0).setProperty(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "address" + ":" + getAddress()+ "," +
            "shortLabel" + ":" + getShortLabel()+ "," +
            "city" + ":" + getCity()+ "," +
            "region" + ":" + getRegion()+ "," +
            "postalCode" + ":" + getPostalCode()+ "," +
            "country" + ":" + getCountry()+ "," +
            "propertyType" + ":" + getPropertyType()+ "," +
            "lotSize" + ":" + getLotSize()+ "," +
            "yearBuilt" + ":" + getYearBuilt()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "organization = "+(getOrganization()!=null?Integer.toHexString(System.identityHashCode(getOrganization())):"null");
  }
}