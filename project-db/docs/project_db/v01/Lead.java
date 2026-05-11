/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;
import java.sql.Date;
import java.util.*;

/**
 * -----------------------------------------------------------------------------
 * Sales pipeline
 * -----------------------------------------------------------------------------
 */
// line 187 "../../model-v0.1.ump"
public class Lead extends CanonicalEntity
{

  //------------------------
  // ENUMERATIONS
  //------------------------

  public enum LeadStage { NEW, QUALIFIED, PROPOSAL, NEGOTIATION, WON, LOST }

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Lead Attributes
  private String sourceChannel;
  private LeadStage stage;
  private Decimal estimatedValue;
  private Date qualifiedAt;

  //Lead Associations
  private Client client;
  private User owner;
  private Property property;
  private Deal deal;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Lead(UUID aCanonicalId, DateTime aCreatedAt, DateTime aUpdatedAt, LeadStage aStage)
  {
    super(aCanonicalId, aCreatedAt, aUpdatedAt);
    sourceChannel = null;
    stage = aStage;
    qualifiedAt = null;
  }

  //------------------------
  // INTERFACE
  //------------------------

  public boolean setSourceChannel(String aSourceChannel)
  {
    boolean wasSet = false;
    sourceChannel = aSourceChannel;
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

  public boolean setEstimatedValue(Decimal aEstimatedValue)
  {
    boolean wasSet = false;
    estimatedValue = aEstimatedValue;
    wasSet = true;
    return wasSet;
  }

  public boolean setQualifiedAt(Date aQualifiedAt)
  {
    boolean wasSet = false;
    qualifiedAt = aQualifiedAt;
    wasSet = true;
    return wasSet;
  }

  /**
   * referral, website, walk-in
   */
  public String getSourceChannel()
  {
    return sourceChannel;
  }

  public LeadStage getStage()
  {
    return stage;
  }

  public Decimal getEstimatedValue()
  {
    return estimatedValue;
  }

  public Date getQualifiedAt()
  {
    return qualifiedAt;
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
  public Deal getDeal()
  {
    return deal;
  }

  public boolean hasDeal()
  {
    boolean has = deal != null;
    return has;
  }
  /* Code from template association_SetOptionalOneToMany */
  public boolean setClient(Client aClient)
  {
    boolean wasSet = false;
    Client existingClient = client;
    client = aClient;
    if (existingClient != null && !existingClient.equals(aClient))
    {
      existingClient.removeLead(this);
    }
    if (aClient != null)
    {
      aClient.addLead(this);
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
      existingOwner.removeLead(this);
    }
    if (aOwner != null)
    {
      aOwner.addLead(this);
    }
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
      existingProperty.removeLead(this);
    }
    if (aProperty != null)
    {
      aProperty.addLead(this);
    }
    wasSet = true;
    return wasSet;
  }
  /* Code from template association_SetOptionalOneToOptionalOne */
  public boolean setDeal(Deal aNewDeal)
  {
    boolean wasSet = false;
    if (aNewDeal == null)
    {
      Deal existingDeal = deal;
      deal = null;
      
      if (existingDeal != null && existingDeal.getLead() != null)
      {
        existingDeal.setLead(null);
      }
      wasSet = true;
      return wasSet;
    }

    Deal currentDeal = getDeal();
    if (currentDeal != null && !currentDeal.equals(aNewDeal))
    {
      currentDeal.setLead(null);
    }

    deal = aNewDeal;
    Lead existingLead = aNewDeal.getLead();

    if (!equals(existingLead))
    {
      aNewDeal.setLead(this);
    }
    wasSet = true;
    return wasSet;
  }

  public void delete()
  {
    if (client != null)
    {
      Client placeholderClient = client;
      this.client = null;
      placeholderClient.removeLead(this);
    }
    if (owner != null)
    {
      User placeholderOwner = owner;
      this.owner = null;
      placeholderOwner.removeLead(this);
    }
    if (property != null)
    {
      Property placeholderProperty = property;
      this.property = null;
      placeholderProperty.removeLead(this);
    }
    if (deal != null)
    {
      deal.setLead(null);
    }
    super.delete();
  }


  public String toString()
  {
    return super.toString() + "["+
            "sourceChannel" + ":" + getSourceChannel()+ "]" + System.getProperties().getProperty("line.separator") +
            "  " + "stage" + "=" + (getStage() != null ? !getStage().equals(this)  ? getStage().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "estimatedValue" + "=" + (getEstimatedValue() != null ? !getEstimatedValue().equals(this)  ? getEstimatedValue().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "qualifiedAt" + "=" + (getQualifiedAt() != null ? !getQualifiedAt().equals(this)  ? getQualifiedAt().toString().replaceAll("  ","    ") : "this" : "null") + System.getProperties().getProperty("line.separator") +
            "  " + "client = "+(getClient()!=null?Integer.toHexString(System.identityHashCode(getClient())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "owner = "+(getOwner()!=null?Integer.toHexString(System.identityHashCode(getOwner())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "property = "+(getProperty()!=null?Integer.toHexString(System.identityHashCode(getProperty())):"null") + System.getProperties().getProperty("line.separator") +
            "  " + "deal = "+(getDeal()!=null?Integer.toHexString(System.identityHashCode(getDeal())):"null");
  }
}