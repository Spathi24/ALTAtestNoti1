/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;
import java.sql.Date;

/**
 * -----------------------------------------------------------------------------
 * CRM-side parties
 * -----------------------------------------------------------------------------
 */
// line 159 "../../model-v0.1.ump"
public class Client extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum ProjectStatus { PROPOSED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED }
  public enum LeadStage { NEW, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST }
  public enum InvoiceStatus { DRAFT, SENT, PARTIAL, PAID, OVERDUE, VOID }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Client Attributes
  private String name;
  private String email;
  private String phone;
  private String billingAddress;

  //Client Associations
  private Organization organization;
  private List<Lead> leads;
  private List<Deal> deals;
  private List<Project> projects;
  private List<Invoice> invoices;
  private List<Document> documents;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Client(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, Organization aOrganization)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    name = aName;
    email = null;
    phone = null;
    billingAddress = null;
    boolean didAddOrganization = setOrganization(aOrganization);
    if (!didAddOrganization)
    {
      throw new RuntimeException("Unable to create client due to organization. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    leads = new ArrayList<Lead>();
    deals = new ArrayList<Deal>();
    projects = new ArrayList<Project>();
    invoices = new ArrayList<Invoice>();
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

  public boolean setEmail(String aEmail)
  {
    boolean wasSet = false;
    email = aEmail;
    wasSet = true;
    return wasSet;
  }

  public boolean setPhone(String aPhone)
  {
    boolean wasSet = false;
    phone = aPhone;
    wasSet = true;
    return wasSet;
  }

  public boolean setBillingAddress(String aBillingAddress)
  {
    boolean wasSet = false;
    billingAddress = aBillingAddress;
    wasSet = true;
    return wasSet;
  }

  public String getName()
  {
    return name;
  }

  public String getEmail()
  {
    return email;
  }

  public String getPhone()
  {
    return phone;
  }

  public String getBillingAddress()
  {
    return billingAddress;
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
  /* Code from template association_GetMany */
  public Invoice getInvoice(int index)
  {
    Invoice aInvoice = invoices.get(index);
    return aInvoice;
  }

  public List<Invoice> getInvoices()
  {
    List<Invoice> newInvoices = Collections.unmodifiableList(invoices);
    return newInvoices;
  }

  public int numberOfInvoices()
  {
    int number = invoices.size();
    return number;
  }

  public boolean hasInvoices()
  {
    boolean has = invoices.size() > 0;
    return has;
  }

  public int indexOfInvoice(Invoice aInvoice)
  {
    int index = invoices.indexOf(aInvoice);
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
      existingOrganization.removeClient(this);
    }
    organization.addClient(this);
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
    Client existingClient = aLead.getClient();
    if (existingClient == null)
    {
      aLead.setClient(this);
    }
    else if (!this.equals(existingClient))
    {
      existingClient.removeLead(aLead);
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
      aLead.setClient(null);
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
  /* Code from template association_AddManyToOne */
  public Deal addDeal(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName, Decimal aValue)
  {
    return new Deal(aCanonicalId, aCreatedAt, aUpdatedAt, aName, aValue, this);
  }

  public boolean addDeal(Deal aDeal)
  {
    boolean wasAdded = false;
    if (deals.contains(aDeal)) { return false; }
    Client existingClient = aDeal.getClient();
    boolean isNewClient = existingClient != null && !this.equals(existingClient);
    if (isNewClient)
    {
      aDeal.setClient(this);
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
    //Unable to remove aDeal, as it must always have a client
    if (!this.equals(aDeal.getClient()))
    {
      deals.remove(aDeal);
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
  /* Code from template association_AddManyToOne */
  public Project addProject(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aName)
  {
    return new Project(aCanonicalId, aCreatedAt, aUpdatedAt, aName, this);
  }

  public boolean addProject(Project aProject)
  {
    boolean wasAdded = false;
    if (projects.contains(aProject)) { return false; }
    Client existingClient = aProject.getClient();
    boolean isNewClient = existingClient != null && !this.equals(existingClient);
    if (isNewClient)
    {
      aProject.setClient(this);
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
    //Unable to remove aProject, as it must always have a client
    if (!this.equals(aProject.getClient()))
    {
      projects.remove(aProject);
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
  public static int minimumNumberOfInvoices()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addInvoice(Invoice aInvoice)
  {
    boolean wasAdded = false;
    if (invoices.contains(aInvoice)) { return false; }
    Client existingClient = aInvoice.getClient();
    if (existingClient == null)
    {
      aInvoice.setClient(this);
    }
    else if (!this.equals(existingClient))
    {
      existingClient.removeInvoice(aInvoice);
      addInvoice(aInvoice);
    }
    else
    {
      invoices.add(aInvoice);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeInvoice(Invoice aInvoice)
  {
    boolean wasRemoved = false;
    if (invoices.contains(aInvoice))
    {
      invoices.remove(aInvoice);
      aInvoice.setClient(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addInvoiceAt(Invoice aInvoice, int index)
  {  
    boolean wasAdded = false;
    if(addInvoice(aInvoice))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfInvoices()) { index = numberOfInvoices() - 1; }
      invoices.remove(aInvoice);
      invoices.add(index, aInvoice);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveInvoiceAt(Invoice aInvoice, int index)
  {
    boolean wasAdded = false;
    if(invoices.contains(aInvoice))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfInvoices()) { index = numberOfInvoices() - 1; }
      invoices.remove(aInvoice);
      invoices.add(index, aInvoice);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addInvoiceAt(aInvoice, index);
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
    Client existingClient = aDocument.getClient();
    if (existingClient == null)
    {
      aDocument.setClient(this);
    }
    else if (!this.equals(existingClient))
    {
      existingClient.removeDocument(aDocument);
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
      aDocument.setClient(null);
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
    Organization placeholderOrganization = organization;
    this.organization = null;
    if(placeholderOrganization != null)
    {
      placeholderOrganization.removeClient(this);
    }
    while( !leads.isEmpty() )
    {
      leads.get(0).setClient(null);
    }
    for(int i=deals.size(); i > 0; i--)
    {
      Deal aDeal = deals.get(i - 1);
      aDeal.delete();
    }
    for(int i=projects.size(); i > 0; i--)
    {
      Project aProject = projects.get(i - 1);
      aProject.delete();
    }
    while( !invoices.isEmpty() )
    {
      invoices.get(0).setClient(null);
    }
    while( !documents.isEmpty() )
    {
      documents.get(0).setClient(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "name" + ":" + getName()+ "," +
            "email" + ":" + getEmail()+ "," +
            "phone" + ":" + getPhone()+ "," +
            "billingAddress" + ":" + getBillingAddress()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "organization = "+(getOrganization()!=null?Integer.toHexString(System.identityHashCode(getOrganization())):"null");
  }
}