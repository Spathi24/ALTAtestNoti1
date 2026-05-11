/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

/**
 * A Lead converts to AT MOST one Deal, and a Deal originates from at most one
 * Lead — never many-from-one. Original `* -- 0..1 Lead` was a multiplicity bug.
 */
// line 201 "../../model-v0.1.ump"
public class Deal extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum ProjectStatus { PROPOSED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED }
  public enum LeadStage { NEW, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Deal Attributes
  private String name;
  private Decimal value;
  private LeadStage stage;
  private Date expectedCloseDate;
  private Date actualCloseDate;
  private float probability;

  //Deal Associations
  private Lead lead;
  private Client client;
  private Property property;
  private User owner;
  private List<Project> projects;
  private List<Document> documents;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Deal(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, Decimal aValue, LeadStage aStage, Client aClient)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    value = aValue;
    stage = aStage;
    expectedCloseDate = null;
    actualCloseDate = null;
    probability = 0.0f;
    boolean didAddClient = setClient(aClient);
    if (!didAddClient)
    {
      throw new RuntimeException("Unable to create deal due to client. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    projects = new ArrayList<Project>();
    documents = new ArrayList<Document>();
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

  public boolean setValue(Decimal aValue)
  {
    boolean wasSet = false;
    value = aValue;
    wasSet = true;
    return wasSet;
  }

  public boolean setStage(LeadStage aStage)
  {
    boolean wasSet = false;
    stage = aStage;
    wasSet = true;
    return wasSet;
  }

  public boolean setExpectedCloseDate(Date aExpectedCloseDate)
  {
    boolean wasSet = false;
    expectedCloseDate = aExpectedCloseDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setActualCloseDate(Date aActualCloseDate)
  {
    boolean wasSet = false;
    actualCloseDate = aActualCloseDate;
    wasSet = true;
    return wasSet;
  }

  public boolean setProbability(float aProbability)
  {
    boolean wasSet = false;
    probability = aProbability;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  public Decimal getValue()
  {
    return value;
  }

  public LeadStage getStage()
  {
    return stage;
  }

  public Date getExpectedCloseDate()
  {
    return expectedCloseDate;
  }

  public Date getActualCloseDate()
  {
    return actualCloseDate;
  }

  public float getProbability()
  {
    return probability;
  }
  /* Code from template association_GetOne */
  public Lead getLead()
  {
    return lead;
  }

  public boolean hasLead()
  {
    boolean has = lead != null;
    return has;
  }
  /* Code from template association_GetOne */
  public Client getClient()
  {
    return client;
  }
  /* Code from template association_GetOne */
  public Property getProperty()
  {
    return property;
  }

  public boolean hasProperty()
  {
    boolean has = property != null;
    return has;
  }
  /* Code from template association_GetOne */
  public User getOwner()
  {
    return owner;
  }

  public boolean hasOwner()
  {
    boolean has = owner != null;
    return has;
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
  /* Code from template association_GetMany */
  public Document getDocument(int index)
  {
    Document aDocument = documents.get(index);
    return aDocument;
  }

  public List<Document> getDocuments()
  {
    List<Document> newDocuments = Collections.unmodifiableList(documents);
    return newDocuments;
  }

  public int numberOfDocuments()
  {
    int number = documents.size();
    return number;
  }

  public boolean hasDocuments()
  {
    boolean has = documents.size() > 0;
    return has;
  }

  public int indexOfDocument(Document aDocument)
  {
    int index = documents.indexOf(aDocument);
    return index;
  }
  /* Code from template association_SetOptionalOneToOptionalOne */
  public boolean setLead(Lead aNewLead)
  {
    boolean wasSet = false;
    if (aNewLead == null)
    {
      Lead existingLead = lead;
      lead = null;
      
      if (existingLead != null && existingLead.getDeal() != null)
      {
        existingLead.setDeal(null);
      }
      wasSet = true;
      return wasSet;
    }

    Lead currentLead = getLead();
    if (currentLead != null && !currentLead.equals(aNewLead))
    {
      currentLead.setDeal(null);
    }

    lead = aNewLead;
    Deal existingDeal = aNewLead.getDeal();

    if (!equals(existingDeal))
    {
      aNewLead.setDeal(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOneToMany */
  public boolean setClient(Client aClient)
  {
    boolean wasSet = false;
    if (aClient == null)
    {
      return wasSet;
    }

    Client existingClient = client;
    client = aClient;
    if (existingClient != null && !existingClient.equals(aClient))
    {
      existingClient.removeDeal(this);
    }
    client.addDeal(this);
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setProperty(Property aProperty)
  {
    boolean wasSet = false;
    Property existingProperty = property;
    property = aProperty;
    if (existingProperty != null && !existingProperty.equals(aProperty))
    {
      existingProperty.removeDeal(this);
    }
    if (aProperty != null)
    {
      aProperty.addDeal(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setOwner(User aOwner)
  {
    boolean wasSet = false;
    User existingOwner = owner;
    owner = aOwner;
    if (existingOwner != null && !existingOwner.equals(aOwner))
    {
      existingOwner.removeDeal(this);
    }
    if (aOwner != null)
    {
      aOwner.addDeal(this);
    }
    wasSet = true;
    return wasSet;
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
    Deal existingDeal = aProject.getDeal();
    if (existingDeal == null)
    {
      aProject.setDeal(this);
    }
    else if (!this.equals(existingDeal))
    {
      existingDeal.removeProject(aProject);
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
      aProject.setDeal(null);
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
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfDocuments()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addDocument(Document aDocument)
  {
    boolean wasAdded = false;
    if (documents.contains(aDocument)) { return false; }
    Deal existingDeal = aDocument.getDeal();
    if (existingDeal == null)
    {
      aDocument.setDeal(this);
    }
    else if (!this.equals(existingDeal))
    {
      existingDeal.removeDocument(aDocument);
      addDocument(aDocument);
    }
    else
    {
      documents.add(aDocument);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeDocument(Document aDocument)
  {
    boolean wasRemoved = false;
    if (documents.contains(aDocument))
    {
      documents.remove(aDocument);
      aDocument.setDeal(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addDocumentAt(Document aDocument, int index)
  {  
    boolean wasAdded = false;
    if(addDocument(aDocument))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDocuments()) { index = numberOfDocuments() - 1; }
      documents.remove(aDocument);
      documents.add(index, aDocument);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveDocumentAt(Document aDocument, int index)
  {
    boolean wasAdded = false;
    if(documents.contains(aDocument))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDocuments()) { index = numberOfDocuments() - 1; }
      documents.remove(aDocument);
      documents.add(index, aDocument);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addDocumentAt(aDocument, index);
    }
    return wasAdded;
  }

  public void delete()
  {
    if (lead != null)
    {
      lead.setDeal(null);
    }
    Client placeholderClient = client;
    this.client = null;
    if(placeholderClient != null)
    {
      placeholderClient.removeDeal(this);
    }
    if (property != null)
    {
      Property placeholderProperty = property;
      this.property = null;
      placeholderProperty.removeDeal(this);
    }
    if (owner != null)
    {
      User placeholderOwner = owner;
      this.owner = null;
      placeholderOwner.removeDeal(this);
    }
    while( !projects.isEmpty() )
    {
      projects.get(0).setDeal(null);
    }
    while( !documents.isEmpty() )
    {
      documents.get(0).setDeal(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "probability" + ":" + getProbability()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "value" + "=" + (getValue() != null ? !getValue().equals(this)  ? getValue().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "stage" + "=" + (getStage() != null ? !getStage().equals(this)  ? getStage().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "expectedCloseDate" + "=" + (getExpectedCloseDate() != null ? !getExpectedCloseDate().equals(this)  ? getExpectedCloseDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "actualCloseDate" + "=" + (getActualCloseDate() != null ? !getActualCloseDate().equals(this)  ? getActualCloseDate().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "lead = "+(getLead()!=null?Integer.toHexString(System.identityHashCode(getLead())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "client = "+(getClient()!=null?Integer.toHexString(System.identityHashCode(getClient())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "property = "+(getProperty()!=null?Integer.toHexString(System.identityHashCode(getProperty())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "owner = "+(getOwner()!=null?Integer.toHexString(System.identityHashCode(getOwner())):"null");
  }
}