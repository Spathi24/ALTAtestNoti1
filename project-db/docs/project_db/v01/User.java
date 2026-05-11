/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.util.*;

/**
 * User, Client, Vendor, Property are tenant-scoped — they belong to exactly
 * one Organization for their entire life. Composition makes the tenant
 * boundary explicit and ensures clean tenant offboarding (drop the org → its
 * users/clients/vendors/properties go with it).
 */
// line 145 "../../model-v0.1.ump"
public class User extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum ProjectStatus { PROPOSED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED }
  public enum LeadStage { NEW, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST }
  public enum TaskStatus { TODO, IN_PROGRESS, BLOCKED, DONE, CANCELLED }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //User Attributes
  private String email;
  private String displayName;
  private String role;
  private boolean isActive;

  //User Associations
  private Organization organization;
  private List<Lead> leads;
  private List<Deal> deals;
  private List<Project> projects;
  private List<Task> tasks;
  private List<DailyLog> dailyLogs;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public User(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, String aEmail, String aDisplayName, Organization aOrganization)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    email = aEmail;
    displayName = aDisplayName;
    role = null;
    isActive = false;
    boolean didAddOrganization = setOrganization(aOrganization);
    if (!didAddOrganization)
    {
      throw new RuntimeException("Unable to create user due to organization. See https://manual.umple.org?RE002ViolationofAssociationMultiplicity.html");
    }
    leads = new ArrayList<Lead>();
    deals = new ArrayList<Deal>();
    projects = new ArrayList<Project>();
    tasks = new ArrayList<Task>();
    dailyLogs = new ArrayList<DailyLog>();
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setEmail(String aEmail)
  {
    boolean wasSet = false;
    email = aEmail;
    wasSet = true;
    return wasSet;
  }

  public boolean setDisplayName(String aDisplayName)
  {
    boolean wasSet = false;
    displayName = aDisplayName;
    wasSet = true;
    return wasSet;
  }

  public boolean setRole(String aRole)
  {
    boolean wasSet = false;
    role = aRole;
    wasSet = true;
    return wasSet;
  }

  public boolean setIsActive(boolean aIsActive)
  {
    boolean wasSet = false;
    isActive = aIsActive;
    wasSet = true;
    return wasSet;
  }

  public String getEmail()
  {
    return email;
  }

  public String getDisplayName()
  {
    return displayName;
  }

  /**
   * PM, Sales, Admin, Field, etc.
   */
  public String getRole()
  {
    return role;
  }

  public boolean getIsActive()
  {
    return isActive;
  }
  /* Code from template attribute_IsBoolean */
  public boolean isIsActive()
  {
    return isActive;
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
  public Task getTask(int index)
  {
    Task aTask = tasks.get(index);
    return aTask;
  }

  public List<Task> getTasks()
  {
    List<Task> newTasks = Collections.unmodifiableList(tasks);
    return newTasks;
  }

  public int numberOfTasks()
  {
    int number = tasks.size();
    return number;
  }

  public boolean hasTasks()
  {
    boolean has = tasks.size() > 0;
    return has;
  }

  public int indexOfTask(Task aTask)
  {
    int index = tasks.indexOf(aTask);
    return index;
  }
  /* Code from template association_GetMany */
  public DailyLog getDailyLog(int index)
  {
    DailyLog aDailyLog = dailyLogs.get(index);
    return aDailyLog;
  }

  public List<DailyLog> getDailyLogs()
  {
    List<DailyLog> newDailyLogs = Collections.unmodifiableList(dailyLogs);
    return newDailyLogs;
  }

  public int numberOfDailyLogs()
  {
    int number = dailyLogs.size();
    return number;
  }

  public boolean hasDailyLogs()
  {
    boolean has = dailyLogs.size() > 0;
    return has;
  }

  public int indexOfDailyLog(DailyLog aDailyLog)
  {
    int index = dailyLogs.indexOf(aDailyLog);
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
      existingOrganization.removeUser(this);
    }
    organization.addUser(this);
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
    User existingOwner = aLead.getOwner();
    if (existingOwner == null)
    {
      aLead.setOwner(this);
    }
    else if (!this.equals(existingOwner))
    {
      existingOwner.removeLead(aLead);
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
      aLead.setOwner(null);
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
    User existingOwner = aDeal.getOwner();
    if (existingOwner == null)
    {
      aDeal.setOwner(this);
    }
    else if (!this.equals(existingOwner))
    {
      existingOwner.removeDeal(aDeal);
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
      aDeal.setOwner(null);
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
    User existingProjectManager = aProject.getProjectManager();
    if (existingProjectManager == null)
    {
      aProject.setProjectManager(this);
    }
    else if (!this.equals(existingProjectManager))
    {
      existingProjectManager.removeProject(aProject);
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
      aProject.setProjectManager(null);
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
  public static int minimumNumberOfTasks()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addTask(Task aTask)
  {
    boolean wasAdded = false;
    if (tasks.contains(aTask)) { return false; }
    User existingAssignee = aTask.getAssignee();
    if (existingAssignee == null)
    {
      aTask.setAssignee(this);
    }
    else if (!this.equals(existingAssignee))
    {
      existingAssignee.removeTask(aTask);
      addTask(aTask);
    }
    else
    {
      tasks.add(aTask);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeTask(Task aTask)
  {
    boolean wasRemoved = false;
    if (tasks.contains(aTask))
    {
      tasks.remove(aTask);
      aTask.setAssignee(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addTaskAt(Task aTask, int index)
  {  
    boolean wasAdded = false;
    if(addTask(aTask))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfTasks()) { index = numberOfTasks() - 1; }
      tasks.remove(aTask);
      tasks.add(index, aTask);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveTaskAt(Task aTask, int index)
  {
    boolean wasAdded = false;
    if(tasks.contains(aTask))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfTasks()) { index = numberOfTasks() - 1; }
      tasks.remove(aTask);
      tasks.add(index, aTask);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addTaskAt(aTask, index);
    }
    return wasAdded;
  }
  /* Code from template association_MinimumNumberOfMethod */
  public static int minimumNumberOfDailyLogs()
  {
    return 0;
  }
  /* Code from template association_AddManyToOptionalOne */
  public boolean addDailyLog(DailyLog aDailyLog)
  {
    boolean wasAdded = false;
    if (dailyLogs.contains(aDailyLog)) { return false; }
    User existingAuthor = aDailyLog.getAuthor();
    if (existingAuthor == null)
    {
      aDailyLog.setAuthor(this);
    }
    else if (!this.equals(existingAuthor))
    {
      existingAuthor.removeDailyLog(aDailyLog);
      addDailyLog(aDailyLog);
    }
    else
    {
      dailyLogs.add(aDailyLog);
    }
    wasAdded = true;
    return wasAdded;
  }

  public boolean removeDailyLog(DailyLog aDailyLog)
  {
    boolean wasRemoved = false;
    if (dailyLogs.contains(aDailyLog))
    {
      dailyLogs.remove(aDailyLog);
      aDailyLog.setAuthor(null);
      wasRemoved = true;
    }
    return wasRemoved;
  }
  /* Code from template association_AddIndexControlFunctions */
  public boolean addDailyLogAt(DailyLog aDailyLog, int index)
  {  
    boolean wasAdded = false;
    if(addDailyLog(aDailyLog))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDailyLogs()) { index = numberOfDailyLogs() - 1; }
      dailyLogs.remove(aDailyLog);
      dailyLogs.add(index, aDailyLog);
      wasAdded = true;
    }
    return wasAdded;
  }

  public boolean addOrMoveDailyLogAt(DailyLog aDailyLog, int index)
  {
    boolean wasAdded = false;
    if(dailyLogs.contains(aDailyLog))
    {
      if(index < 0 ) { index = 0; }
      if(index > numberOfDailyLogs()) { index = numberOfDailyLogs() - 1; }
      dailyLogs.remove(aDailyLog);
      dailyLogs.add(index, aDailyLog);
      wasAdded = true;
    } 
    else 
    {
      wasAdded = addDailyLogAt(aDailyLog, index);
    }
    return wasAdded;
  }

  public void delete()
  {
    Organization placeholderOrganization = organization;
    this.organization = null;
    if(placeholderOrganization != null)
    {
      placeholderOrganization.removeUser(this);
    }
    while( !leads.isEmpty() )
    {
      leads.get(0).setOwner(null);
    }
    while( !deals.isEmpty() )
    {
      deals.get(0).setOwner(null);
    }
    while( !projects.isEmpty() )
    {
      projects.get(0).setProjectManager(null);
    }
    while( !tasks.isEmpty() )
    {
      tasks.get(0).setAssignee(null);
    }
    while( !dailyLogs.isEmpty() )
    {
      dailyLogs.get(0).setAuthor(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "email" + ":" + getEmail()+ "," +
            "displayName" + ":" + getDisplayName()+ "," +
            "role" + ":" + getRole()+ "," +
            "isActive" + ":" + getIsActive()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "organization = "+(getOrganization()!=null?Integer.toHexString(System.identityHashCode(getOrganization())):"null");
  }
}